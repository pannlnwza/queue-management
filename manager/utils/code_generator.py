import random
import string

def generate_unique_code(model_class, field_name="code", length=12):
    """
    Generate a unique code for a given model class.

    Args:
        model_class (models.Model): The Django model class to check uniqueness against.
        field_name (str): The field name to check for uniqueness. Default is 'code'.
        length (int): The length of the code to generate. Default is 12.

    Returns:
        str: A unique code.
    """
    characters = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(characters, k=length))
        # Check if the code is unique in the specified field
        if not model_class.objects.filter(**{field_name: code}).exists():
            return code

def generate_unique_number(model_class):
    """
    Generate a unique number for a participant in the format A001 to A999, B001, etc.
    """
    last_participant = model_class.objects.order_by('-joined_at').first()
    if last_participant and last_participant.number:
        # Extract the last prefix and number
        last_prefix = last_participant.number[0]
        last_number = int(last_participant.number[1:])
        if last_number < 999:
            # Increment the number while keeping the same prefix
            return f"{last_prefix}{last_number + 1:03d}"
        else:
            # Move to the next prefix
            next_prefix = chr(ord(last_prefix) + 1)
            return f"{next_prefix}001"
    else:
        # Default to A001 if no participants exist
        return "A001"
