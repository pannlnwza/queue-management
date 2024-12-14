import random
import string
from django.db import transaction

def generate_unique_code(model_class, field_name="code", length=12, max_retries=10):
    """
    Generates a unique code for a model instance.

    :param model_class: The model class to check for existing codes. This should be a Django model.
    :param field_name: The field name where the code should be checked. Default is 'code'.
    :param length: The length of the generated code. Default is 12 characters.
    :param max_retries: The maximum number of retries if a code collision occurs. Default is 10.

    :return: A unique code that is not already used in the specified model.

    :raises ValueError: If a unique code cannot be generated after the specified number of retries.
    """
    characters = string.ascii_uppercase + string.digits
    for _ in range(max_retries):
        code = ''.join(random.choices(characters, k=length))
        if not model_class.objects.filter(**{field_name: code}).exists():
            return code
    raise ValueError(f"Could not generate a unique code after {max_retries} retries")


def generate_unique_number(queue):
    """
    Generates a unique participant number for a given queue.

    :param queue: The queue instance for which the participant number is being generated.

    :return: A unique participant number, formatted as a string.

    :raises ValueError: If the number generation logic fails unexpectedly.
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
