import random
import string
from django.db import transaction

def generate_unique_code(model_class, field_name="code", length=12, max_retries=10):
    """
    Generate a unique code for a given model class.

    Args:
        model_class (models.Model): The Django model class to check uniqueness against.
        field_name (str): The field name to check for uniqueness. Default is 'code'.
        length (int): The length of the code to generate. Default is 12.
        max_retries (int): Maximum retries before raising an exception. Default is 10.

    Returns:
        str: A unique code.

    Raises:
        ValueError: If a unique code cannot be generated within max_retries attempts.
    """
    characters = string.ascii_uppercase + string.digits
    for _ in range(max_retries):
        code = ''.join(random.choices(characters, k=length))
        if not model_class.objects.filter(**{field_name: code}).exists():
            return code
    raise ValueError(f"Could not generate a unique code after {max_retries} retries")


def generate_unique_number(queue):
    """
    Generate a unique number for a participant in the format A001 to A999, B001, etc.
    Args:
        queue (Queue): The queue instance for which to generate the number.
    Returns:
        str: A unique participant number.
    """
    with transaction.atomic():
        last_participant = queue.participant_set.select_for_update().order_by('-joined_at').first()
        if last_participant and last_participant.number:
            last_prefix = last_participant.number[0]
            last_number = int(last_participant.number[1:])
            if last_number < 999:
                return f"{last_prefix}{last_number + 1:03d}"
            else:
                next_prefix = chr(ord(last_prefix) + 1)
                return f"{next_prefix}001"
        else:
            return "A001"
