from django.db import models

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


class Bike(models.Model):
    type = models.CharField(max_length=150)
    name = models.CharField(max_length=150)
    size = models.CharField(max_length=150)
    color = models.CharField(max_length=150)

    def __str__(self):
        return f"{self.type} {self.name} {self.size} {self.color}"