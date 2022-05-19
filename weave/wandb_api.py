from wandb.apis import public
from .context import _wandb_api_key


def wandb_public_api():
    return public.Api(api_key=_wandb_api_key.get())