import {
  NodeOrVoidNode,
  callOpVeryUnsafe,
  constString,
  constNone,
  maybe,
  opGet,
} from '@wandb/weave/core';
import {useNodeValueExecutor, useMakeMutation} from '@wandb/weave/react';
import {useState, useCallback} from 'react';
import {
  isServedLocally,
  isRemoteURI,
  isLocalURI,
  uriFromNode,
  toArtifactSafeName,
} from './util';

type LocalPersistenceStateId =
  | 'local_untracked'
  | 'local_saved_no_remote'
  | 'local_uncommitted_with_remote'
  | 'local_published';

type CloudPersistenceStateId =
  | 'cloud_untracked'
  | 'cloud_saved_no_remote'
  | 'cloud_uncommitted_with_remote'
  | 'cloud_published';

export type PersistenceState =
  | LocalPersistenceStateId
  | CloudPersistenceStateId;

export type PersistenceDeleteActionType = 'delete_local' | 'delete_remote';
export type PersistenceRenameActionType =
  | 'rename_local' // Only applicable when no remote branch exists
  | 'publish_as' // (publishes a dirty local branch or untracked with remote to a new remote branch)
  | 'rename_remote'; // Directly renames a remote branch (effectively a re-publish) - not supported by backend today.
export type PersistenceStoreActionType =
  | 'save' // Start tracking changes locally
  | 'commit' // Commits local changes to remote branch directly
  | 'publish_new'; // Pushes local without remote to a new remote branch (uses current name)

export type PersistenceAction =
  | PersistenceDeleteActionType
  | PersistenceRenameActionType
  | PersistenceStoreActionType;

const actionsRequiringAuthentication: Set<PersistenceAction> = new Set([
  'commit',
  'publish_as',
  'publish_new',
  'rename_remote',
  'delete_remote',
]);

type ActionSetType = {
  storeAction: PersistenceStoreActionType | null;
  renameAction: PersistenceRenameActionType | null;
  deleteAction: PersistenceDeleteActionType | null;
};

// Note: each action should have at most 1 rename action and 1 publish/commit/save action
const persistenceActions: {
  [startState in PersistenceState]: ActionSetType;
} = {
  local_untracked: {
    storeAction: 'save',
    renameAction: 'publish_as',
    deleteAction: 'delete_local',
  },
  local_saved_no_remote: {
    storeAction: 'publish_new',
    renameAction: 'rename_local',
    deleteAction: 'delete_local',
  },
  local_uncommitted_with_remote: {
    storeAction: 'commit',
    renameAction: 'publish_as',
    deleteAction: 'delete_local',
  },
  local_published: {
    storeAction: null,
    renameAction: null, // 'rename_remote' - uncomment after implementing
    deleteAction: 'delete_local',
  },
  cloud_untracked: {
    storeAction: null,
    renameAction: 'publish_as',
    deleteAction: 'delete_remote',
  },
  cloud_saved_no_remote: {
    storeAction: 'publish_new',
    renameAction: 'publish_as',
    deleteAction: 'delete_remote',
  },
  cloud_uncommitted_with_remote: {
    storeAction: 'commit',
    renameAction: 'publish_as',
    deleteAction: 'delete_remote',
  },
  cloud_published: {
    storeAction: null,
    renameAction: null, // 'rename_remote' - uncomment after implementing
    deleteAction: 'delete_remote',
  },
};

type NodeForm =
  | 'untracked'
  | 'local_no_remote'
  | 'local_with_remote'
  | 'published';

const stateFromURI = (
  uri: string | null,
  hasRemote: boolean
): PersistenceState => {
  const local = isServedLocally();
  let form: NodeForm = 'untracked';
  if (uri == null) {
    form = 'untracked';
  } else if (isRemoteURI(uri)) {
    form = 'published';
  } else if (isLocalURI(uri)) {
    if (hasRemote) {
      form = 'local_with_remote';
    } else {
      form = 'local_no_remote';
    }
  }

  let state: PersistenceState;

  if (local) {
    switch (form) {
      case 'untracked':
        state = 'local_untracked';
        break;
      case 'local_no_remote':
        state = 'local_saved_no_remote';
        break;
      case 'local_with_remote':
        state = 'local_uncommitted_with_remote';
        break;
      case 'published':
        state = 'local_published';
        break;
      default:
        throw new Error(`Unexpected form: ${form}`);
    }
  } else {
    switch (form) {
      case 'untracked':
        state = 'cloud_untracked';
        break;
      case 'local_no_remote':
        state = 'cloud_saved_no_remote';
        break;
      case 'local_with_remote':
        state = 'cloud_uncommitted_with_remote';
        break;
      case 'published':
        state = 'cloud_published';
        break;
      default:
        throw new Error(`Unexpected form: ${form}`);
    }
  }

  return state;
};

export const getAvailableActions = (
  state: PersistenceState,
  isAuthenticated: boolean
): ActionSetType => {
  const actions = persistenceActions[state];
  if (!isAuthenticated) {
    return {
      storeAction:
        actions.storeAction != null &&
        actionsRequiringAuthentication.has(actions.storeAction)
          ? null
          : actions.storeAction,
      renameAction:
        actions.renameAction != null &&
        actionsRequiringAuthentication.has(actions.renameAction)
          ? null
          : actions.renameAction,
      deleteAction:
        actions.deleteAction != null &&
        actionsRequiringAuthentication.has(actions.deleteAction)
          ? null
          : actions.deleteAction,
    };
  }
  return actions;
};

export type TakeActionType = (
  action: PersistenceAction,
  actionOptions?:
    | {
        [key: string]: string;
      }
    | undefined,
  onActionFinished?: () => void
) => Promise<void>;

export const useStateMachine = (
  inputNode: NodeOrVoidNode,
  updateNode: (node: NodeOrVoidNode) => void,
  hasRemote: boolean
) => {
  const uri = uriFromNode(inputNode);
  const nodeState = stateFromURI(uri, hasRemote);
  const executor = useNodeValueExecutor();
  const makeMutation = useMakeMutation();
  const [acting, setActing] = useState(false);
  const takeAction: TakeActionType = useCallback(
    async (
      action: PersistenceAction,
      actionOptions?: {[key: string]: string},
      onActionFinished?: () => void
    ) => {
      setActing(true);
      actionOptions = actionOptions || {};

      if (
        persistenceActions[nodeState].storeAction !== action &&
        persistenceActions[nodeState].renameAction !== action &&
        persistenceActions[nodeState].deleteAction !== action
      ) {
        throw new Error(`Invalid action: ${action}`);
      }
      if (action === 'save') {
        const saveNode = callOpVeryUnsafe(
          'save_to_uri',
          {
            obj: inputNode,
            name:
              actionOptions.name != null
                ? constString(actionOptions.name)
                : constNone(),
          },
          maybe('string')
        );
        const saveUri: string | null = await executor(saveNode as any);
        if (saveUri == null) {
          throw new Error(`Failed to save`);
        }
        updateNode(opGet({uri: constString(saveUri)}));
      } else if (action === 'rename_local') {
        const newName = toArtifactSafeName(actionOptions.name);
        await makeMutation(inputNode, 'rename_artifact', {
          name: constString(newName),
        });
        // NOTICE: This should only occur for local artifacts
        // TODO: Support various aliases?
        updateNode(
          opGet({
            uri: constString(`local-artifact:///${newName}:latest/obj`),
          })
        );
      } else if (action === 'publish_as' || action === 'publish_new') {
        await makeMutation(
          inputNode,
          'publish_artifact',
          {
            artifact_name:
              actionOptions.name != null
                ? constString(toArtifactSafeName(actionOptions.name))
                : constNone(),
            project_name:
              actionOptions.projectName != null
                ? constString(actionOptions.projectName)
                : constString('weave'),
            entity_name:
              actionOptions.entityName != null
                ? constString(actionOptions.entityName)
                : constNone(),
          },
          newRoot => {
            updateNode(newRoot);
          }
        );
      } else if (action === 'commit') {
        await makeMutation(inputNode, 'merge_artifact', {}, newRoot => {
          updateNode(newRoot);
        });
      } else if (action === 'delete_local' || action === 'delete_remote') {
        await makeMutation(inputNode, 'delete_artifact', {});
      } else {
        throw new Error(`Not implemented yet: ${action}`);
      }
      setActing(false);
      if (onActionFinished) {
        onActionFinished();
      }
    },
    [executor, inputNode, makeMutation, nodeState, updateNode]
  );

  return {nodeState, takeAction, acting};
};
