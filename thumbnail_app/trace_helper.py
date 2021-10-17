import inspect
from functools import wraps


def get_func_arguments(func, *args, **kwargs):
    bound_args = inspect.signature(func).bind(*args, **kwargs)
    bound_args.apply_defaults()
    return {
        f"arguments.{k}": v if type(v) in [bool, str, bytes, int, float] else f"{v}"
        for k, v in bound_args.arguments.items()
    }


def trace_function(tracer, name: str = None, capture_args: bool = True):
    """
    이 함수는 아래와 같은 with 구문을 축약한 데코레이터입니다
    def func_name(*args):
        with tracer.start_as_current_span(func_name) as span:
            span.set_attributes({
                args1_name:args1_value,
                args2_name:args2_value,
            })
            ***
    """

    def decorator(func):
        trace_name = name or func.__qualname__

        @wraps(func)
        def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(trace_name) as span:
                if capture_args:
                    span.set_attributes(get_func_arguments(func, *args, **kwargs))
                return func(*args, **kwargs)

        return wrapper

    return decorator
