def extract_data_variables(data):
    """
    Extracts key-value pairs from a dictionary.

    :param data: The dictionary from which key-value pairs are extracted.
    :return: A dictionary with the same key-value pairs from the input data.
    """
    return {key: value for key, value in data.items()}


def format_duration(duration_minutes: int) -> str:
    """
    Formats a duration given in minutes into a readable string.

    :param duration_minutes: The duration in minutes to format.
    :return: A string representing the formatted duration.
    """
    if duration_minutes == 1:
        return "1 min"
    elif duration_minutes < 60:
        return f"{duration_minutes} mins"
    hours = duration_minutes // 60
    minutes = duration_minutes % 60
    if minutes == 1:
        return f"{hours} hr {minutes} min"
    return f"{hours} hr {minutes} mins"
