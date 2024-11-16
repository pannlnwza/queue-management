def extract_data_variables(data):
    return {key: value for key, value in data.items()}


def format_duration(duration_minutes: int) -> str:
    """Helper function to format duration in 'X hr Y min' or 'X min'."""
    if duration_minutes == 1:
        return f"1 min"
    elif duration_minutes < 60:
        return f"{duration_minutes} mins"
    hours = duration_minutes // 60
    minutes = duration_minutes % 60
    if minutes == 1:
        return f"{hours} hr {minutes} min"
    return f"{hours} hr {minutes} mins"
