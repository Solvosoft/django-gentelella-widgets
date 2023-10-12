from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

# Create your models here.
from djgentelella.fields.catalog import GTForeignKey, GTManyToManyField, GTOneToOneField


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


class RelPerson(models.Model):
    description = models.CharField(max_length=150)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    number = models.IntegerField()

    def __str__(self):
        return self.description

class Catalog(models.Model):
    key = models.CharField(max_length=150)
    description = models.CharField(max_length=500)

    def __str__(self):
        return self.key + " - " + self.description


class WithCatalog(models.Model):
    mycatalog = GTForeignKey(
        Catalog, on_delete=models.DO_NOTHING, key_name="key", key_value="Options")
    countries = GTManyToManyField(
        Catalog, related_name="countryrel", key_name="key", key_value="countries")

    def __str__(self):
        return str(self.mycatalog)


class OneCatalog(models.Model):
    me = GTOneToOneField(Catalog, on_delete=models.CASCADE,
                         key_name="key", key_value="countries")

    def __str__(self):
        return str(self.me)


class Foo(models.Model):
    age = models.IntegerField(validators=[
        MaxValueValidator(120),
        MinValueValidator(1)
    ])
    speed_in_miles_per_hour = models.FloatField(validators=[
        MinValueValidator(1),
        MaxValueValidator(50)
    ])
    number_of_eyes = models.IntegerField(validators=[
        MinValueValidator(0),
        MaxValueValidator(10)
    ])


class PeopleGroup(models.Model):
    name = models.CharField(max_length=150)
    people = models.ManyToManyField(Person)
    comunities = models.ManyToManyField('Comunity')
    country = models.ForeignKey(
        Country, null=True, blank=True, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Comunity(models.Model):
    name = models.CharField(max_length=150)

    def __str__(self):
        return self.name


class A(models.Model):
    display = models.CharField(max_length=150)


class B(models.Model):
    display = models.CharField(max_length=150)
    a = models.ForeignKey(A, on_delete=models.CASCADE)


class C(models.Model):
    display = models.CharField(max_length=150)
    b = models.ForeignKey(B, on_delete=models.CASCADE)


class D(models.Model):
    display = models.CharField(max_length=150)
    c = models.ForeignKey(C, on_delete=models.CASCADE)


class E(models.Model):
    display = models.CharField(max_length=150)
    d = models.ForeignKey(D, on_delete=models.CASCADE)


class ABCDE(models.Model):
    a = models.ManyToManyField(A)
    b = models.ForeignKey(B, on_delete=models.CASCADE)
    c = models.ManyToManyField(C)
    d = models.ForeignKey(D, on_delete=models.CASCADE)
    e = models.ManyToManyField(E)

    def __str__(self):
        return " ".join([x.display for x in self.e.all()])


def validate_inputs(value):
    if value.find('_') != -1:
        raise ValidationError(
            _('%(value)s need more digits'), params={'value': value}, )


def validate_email(value):
    position = value.split('@')
    if value.find('_') != -1 and len(position[0]) > 0 and len(position[1]) > 4:
        raise ValidationError(_('that email invalid'))


def validate_credit_card(value):
    position = value.split('_')
    value = position[0]
    if len(value) < 13:
        raise ValidationError(_('that card invalid'))

    return value


class InputMask(models.Model):
    date = models.DateField()
    phone = models.CharField(max_length=14, validators=[validate_inputs])
    serial_number = models.CharField(
        max_length=23, validators=[validate_inputs])
    taxid = models.CharField(max_length=11, validators=[validate_inputs])
    credit_card = models.CharField(
        max_length=19, validators=[validate_credit_card])
    email = models.EmailField(validators=[validate_email])

    def __str__(self):
        return str(self.id) + ' - ' + self.email


class DateRange(models.Model):
    date_range = models.CharField(max_length=25)
    date_custom = models.CharField(max_length=25)
    date_time = models.CharField(max_length=45)


class TaggingModel(models.Model):
    text_list = models.CharField(max_length=500, null=True, blank=True)
    email_list = models.CharField(max_length=500, null=True, blank=True)
    area_list = models.TextField(null=True, blank=True)


class WysiwygModel(models.Model):
    information = models.TextField()
    extra_information = models.TextField()


class YesNoInput(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)
    is_public = models.BooleanField(default=False)
    has_copies = models.BooleanField(default=False)
    copy_number = models.IntegerField(default=0)
    has_meta = models.BooleanField(default=False)
    year = models.IntegerField(default=2020)
    editorial = models.CharField(max_length=250, default='')
    display_publish = models.BooleanField(default=False)


class gridSlider(models.Model):
    minimum = models.IntegerField()
    maximum = models.IntegerField()
    datetime = models.DateTimeField()
    age = models.IntegerField()


class Employee(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    username = models.CharField(max_length=100)

    # username also can be a @property to user.username.

    @property
    def gt_get_permission(self):
        return self.user.user_permissions

    def __str__(self):
        return self.username


class ChunkedUploadItem(models.Model):
    name = models.CharField(max_length=100)
    fileexample = models.FileField(upload_to='filedemo')


class Calendar(models.Model):
    title = models.CharField(max_length=255)
    options = models.JSONField(null=True, blank=True)
    events = models.JSONField(null=True, blank=True)


class Event(models.Model):
    calendar = models.ForeignKey(to=Calendar, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, null=True, blank=True)
    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title
