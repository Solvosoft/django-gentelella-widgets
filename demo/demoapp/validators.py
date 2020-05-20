from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator

def validate_age_value(value):
    MinValueValidator(1)(value)
    MaxValueValidator(120)(value)
    return value

def validate_speed_value(value):
    MinValueValidator(1)(value)
    MaxValueValidator(50)(value)
    return value

def validate_eyes_number(value):
    MinValueValidator(0)(value)
    MaxValueValidator(10)(value)
    return value

