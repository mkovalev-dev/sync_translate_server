from pydantic import BaseModel


class UserCreateModel(BaseModel):
    first_name: str
    last_name: str
    username: str


class UserSignInModel(BaseModel):
    username: str
