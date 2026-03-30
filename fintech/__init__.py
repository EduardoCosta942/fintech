def request(user_prompt: str):
	from .services import request as _request
	return _request(user_prompt)

__all__ = ['request', 'models', 'logger']