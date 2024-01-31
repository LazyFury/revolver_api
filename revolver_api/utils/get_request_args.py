

def get_instance_from_kwargs(cls, kwargs):
    """_summary_

    Args:
        cls (_type_): _description_
        kwargs (_type_): _description_

    Returns:
        _type_: _description_
    """
    for k, v in kwargs.items():
        if isinstance(v, cls):
            return v

def get_instance_from_args(cls, args):
    """_summary_

    Args:
        cls (_type_): _description_
        args (_type_): _description_

    Returns:
        _type_: _description_
    """
    for v in args:
        if isinstance(v, cls):
            return v
        
def get_instance_from_args_or_kwargs(cls, args, kwargs):
    """### 从参数或者关键字参数中获取实例

    Args:
        cls (_type_): _description_
        args (_type_): _description_
        kwargs (_type_): _description_

    Returns:
        _type_: _description_
    """
    return get_instance_from_args(cls, args) or get_instance_from_kwargs(cls, kwargs)