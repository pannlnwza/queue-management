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
