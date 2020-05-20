from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


# Create your models here.

class Country(models.Model):
    name = models.CharField(max_length=150)

    def __str__(self):
        return self.name

class Person(models.Model):
    name = models.CharField(max_length=150)
    num_children = models.IntegerField(default=0)
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    born_date = models.DateField()
    last_time = models.DateTimeField()

    def __str__(self):
        return self.name

class Foo(models.Model):
    age = models.IntegerField(validators=
                                    [
                                        MaxValueValidator(120),
                                        MinValueValidator(1)
                                    ])
    speed_in_miles_per_hour = models.FloatField(validators=
                                    [
                                        MinValueValidator(1),
                                        MaxValueValidator(50)
                                    ])
    number_of_eyes = models.IntegerField(validators=
                                    [
                                        MinValueValidator(0),
                                        MaxValueValidator(10)
                                    ])