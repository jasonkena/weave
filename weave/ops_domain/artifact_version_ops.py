import logging
import typing

from . import wb_util

from . import file_wbartifact
from ..api import op
from . import wb_domain_types
from . import wbartifact
from . import wandb_domain_gql
from .. import weave_types as types
from .. import refs
from .. import artifacts_local
from urllib.parse import quote


@op(name="artifactVersion-link")
def artifact_version_link(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> wb_domain_types.Link:
    return wb_domain_types.Link(
        f"{artifactVersion._artifact_sequence.artifact_collection_name}:v{artifactVersion.version_index}",
        f"/{artifactVersion._artifact_sequence._project._entity.entity_name}/{artifactVersion._artifact_sequence._project.project_name}/artifacts/{quote(artifactVersion.sdk_obj.type)}/{quote(artifactVersion._artifact_sequence.artifact_collection_name)}/v{artifactVersion.version_index}",
    )


@op(name="artifactVersion-createdBy")
def artifact_version_created_by(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> typing.Optional[wb_domain_types.Run]:
    return wandb_domain_gql.artifact_version_created_by(artifactVersion)


@op(name="artifactVersion-isWeaveObject")
def artifact_version_is_weave_object(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> bool:
    # TODO: this needs a query.
    return False


@op(name="artifactVersion-aliases")
def artifact_version_aliases(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> list[wb_domain_types.ArtifactAlias]:
    return wandb_domain_gql.artifact_version_aliases(artifactVersion)


@op(name="artifactVersion-artifactCollections")
def artifact_version_artifact_collections(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> list[wb_domain_types.ArtifactCollection]:
    return wandb_domain_gql.artifact_version_artifact_collections(artifactVersion)


@op(name="artifactVersion-memberships")
def artifact_version_memberships(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> list[wb_domain_types.ArtifactCollectionMembership]:
    return wandb_domain_gql.artifact_version_memberships(artifactVersion)


@op(name="artifactVersion-createdByUser")
def artifact_version_created_by_user(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> typing.Optional[wb_domain_types.User]:
    return wandb_domain_gql.artifact_version_created_by_user(artifactVersion)


@op(name="artifactVersion-artifactType")
def artifact_version_artifact_type(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> wb_domain_types.ArtifactType:
    return wandb_domain_gql.artifact_collection_artifact_type(
        artifactVersion._artifact_sequence
    )


@op(name="artifactVersion-artifactSequence")
def artifact_version_artifact_sequence(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> wb_domain_types.ArtifactCollection:
    return artifactVersion._artifact_sequence


@op(name="artifactVersion-usedBy")
def artifact_version_used_by(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> list[wb_domain_types.Run]:
    # TODO: Convert this to it's own query
    res: list[wb_domain_types.Run] = []
    for r in artifactVersion.sdk_obj.used_by():
        if len(res) == 50:
            break
        res.append(
            wb_domain_types.Run(
                _project=wb_domain_types.Project(
                    _entity=wb_domain_types.Entity(r.entity),
                    project_name=r.project,
                ),
                run_id=r.id,
            )
        )
    return res


@op(name="artifactVersion-id")
def id(artifactVersion: wb_domain_types.ArtifactVersion) -> str:
    return artifactVersion.sdk_obj.id


@op(name="artifactVersion-name")
def name(artifactVersion: wb_domain_types.ArtifactVersion) -> str:
    return artifactVersion.sdk_obj.name


@op(name="artifactVersion-digest")
def digest(artifactVersion: wb_domain_types.ArtifactVersion) -> str:
    return artifactVersion.sdk_obj.digest


@op(name="artifactVersion-size")
def size(artifactVersion: wb_domain_types.ArtifactVersion) -> int:
    return artifactVersion.sdk_obj.size


@op(name="artifactVersion-description")
def description(artifactVersion: wb_domain_types.ArtifactVersion) -> str:
    return artifactVersion.sdk_obj.description


@op(name="artifactVersion-createdAt")
def created_at(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> wb_domain_types.Date:
    return artifactVersion.sdk_obj.created_at


@op(name="artifactVersion-files")
def files(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> list[file_wbartifact.ArtifactVersionFile]:
    # TODO: What is the correct data model here? - def don't want to go download everything
    return []


@op()
def refine_history_metrics(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> types.Type:
    return wb_util.process_run_dict_type({})


@op(name="artifactVersion-historyMetrics", refine_output_type=refine_history_metrics)
def history_metrics(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> dict[str, typing.Any]:
    # TODO: We should probably create a backend endpoint for this... in weave0 we make a bunch on custom calls.
    return {}


@op()
def refine_metadata(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> types.Type:
    return wb_util.process_run_dict_type(artifactVersion.sdk_obj.metadata)


@op(name="artifactVersion-metadata", refine_output_type=refine_metadata)
def metadata(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> dict[str, typing.Any]:
    return wb_util.process_run_dict_obj(artifactVersion.sdk_obj.metadata)


# Special bridge functions to lower level local artifacts


@op(
    name="artifactVersion-file",
    output_type=refs.ArtifactVersionFileType(),
)
def file_(artifactVersion: wb_domain_types.ArtifactVersion, path: str):
    # TODO (tim): This is a total hack - I am not sure why dispatch is sending use these
    if isinstance(artifactVersion, artifacts_local.Artifact):
        logging.warning(
            "Expected input to be of type ArtifactVersion, but got artifacts_local.Artifact in artifactVersion-file"
        )
        art_local = artifactVersion
    else:
        art_local = artifacts_local.WandbArtifact.from_wb_artifact(
            artifactVersion.sdk_obj
        )
    return wbartifact.ArtifactVersion.file.raw_resolve_fn(art_local, path)


@op(
    name="artifactVersion-fileReturnType",
    output_type=types.Type(),
)
def path_type(artifactVersion: wb_domain_types.ArtifactVersion, path: str):
    # TODO (tim): This is a total hack - I am not sure why dispatch is sending use thsese
    if isinstance(artifactVersion, artifacts_local.Artifact):
        logging.warning(
            "Expected input to be of type ArtifactVersion, but got artifacts_local.Artifact in artifactVersion-fileReturnType"
        )
        art_local = artifactVersion
    else:
        art_local = artifacts_local.WandbArtifact.from_wb_artifact(
            artifactVersion.sdk_obj
        )
    return wbartifact.ArtifactVersion.path_type.raw_resolve_fn(art_local, path)