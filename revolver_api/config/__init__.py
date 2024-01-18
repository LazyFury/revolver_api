from pathlib import Path


def readTomlConfig(baseDir:Path):
    """_summary_

    Raises:
        Exception: _description_

    Returns:
        _type_: _description_
    """
    import toml

    configPath = str(baseDir)

    # if file exits
    if not Path(configPath).is_file():
        with open(configPath, "w") as f:
            f.write(
                '[timezone]\ntimezone = "Asia/Shanghai"\ndatetime_format = "%Y-%m-%d %H:%M:%S"'
            )
        raise Exception("config.toml not found,try to create a new one")

    with open(configPath, "r") as f:
        config = toml.load(f)
    return config


def get(config: dict[any],domain:str,default=""):  
    """_summary_

    Args:
        domain (_type_): _description_
        default (str, optional): _description_. Defaults to "".

    Returns:
        _type_: _description_
    """
    keys = domain.split(".")
    target = config
    for key in keys:
        if key in target:
            target = target[key]
        else:
            return default
    return target

