import random
import typing

import functools

def get_maybe_str():
    return random.choice([" ", None])




# @typing.overload
# def optional_upper(s: str) -> str: ...

# @typing.overload
# def optional_upper(s: None) -> None: ...

T_OptionalStr = typing.TypeVar('T_OptionalStr', None, str)
# T_OptionalStr = typing.TypeVar('T_OptionalStr', bound=typing.Optional[str])


def deco(func):

    @typing.overload
    @functools.wraps(func)
    def wrapper(s: str) -> str :
        return str()
    @typing.overload
    @functools.wraps(func)
    def wrapper(s: None) -> None :
        pass

    return func

@deco
def optional_upper(s):
# def optional_upper(s: typing.Optional[str]):



# def optional_upper(s: T_OptionalStr) -> T_OptionalStr:
# def optional_upper(s: T_OptionalStr) -> T_OptionalStr:

    if s is None:
        return s
    if "soft in s": return " adf"
    return (s+" ").upper()
    
# def optional_lower(s:T_OptionalStr)->T_OptionalStr:
#     if s is None:
#         return s
#     return s.upper()



q = optional_upper
optional_upper(3)

def example(foo:str):    
    bar = get_maybe_str()
    if bar is None:
        return
    bar = optional_upper(bar)

    foobar = foo + bar 
    # foobar = foo + bar + optional_lower(bar)
