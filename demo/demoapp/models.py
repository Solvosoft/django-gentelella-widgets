import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericRelation

from djgentelella.fields.catalog import (
    GTForeignKey,
    GTManyToManyField,
    GTOneToOneField,
)
from djgentelella.alerts.models import AbstractAlertEvent, AbstractAlertRule
from djgentelella.fields.maps import GTPointField
from djgentelella.models import DeletedWithTrash

User = get_user_model()


class Country(models.Model):
    name = models.CharField(max_length=150)
    # ISO 3166-1 alpha-2, the code the flag sprite is indexed by. Feeds
    # CountryFlagLookup.get_url() -> djgentelella.flags.flag_url().
    code = models.CharField(max_length=8, blank=True, default='')

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


class Catalog(models.Model):
    key = models.CharField(max_length=150)
    description = models.CharField(max_length=500)

    def __str__(self):
        return self.key + ' - ' + self.description


class WithCatalog(models.Model):
    mycatalog = GTForeignKey(
        Catalog, on_delete=models.DO_NOTHING, key_name='key', key_value='Options'
    )
    countries = GTManyToManyField(
        Catalog, related_name='countryrel', key_name='key', key_value='countries'
    )

    def __str__(self):
        return str(self.mycatalog)


class OneCatalog(models.Model):
    me = GTOneToOneField(
        Catalog, on_delete=models.CASCADE, key_name='key', key_value='countries'
    )

    def __str__(self):
        return str(self.me)


class Foo(models.Model):
    age = models.IntegerField(validators=[MaxValueValidator(120), MinValueValidator(1)])
    speed_in_miles_per_hour = models.FloatField(
        validators=[MinValueValidator(1), MaxValueValidator(50)]
    )
    number_of_eyes = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )


class PeopleGroup(models.Model):
    name = models.CharField(max_length=150)
    people = models.ManyToManyField(Person)
    communities = models.ManyToManyField('Community')
    country = models.ForeignKey(
        Country, null=True, blank=True, on_delete=models.CASCADE
    )

    def __str__(self):
        return self.name


class Community(models.Model):
    name = models.CharField(max_length=150)

    def __str__(self):
        return self.name


class A(models.Model):
    display = models.CharField(max_length=150)

    def __str__(self):
        return self.display


class B(models.Model):
    display = models.CharField(max_length=150)
    a = models.ForeignKey(A, on_delete=models.CASCADE)

    def __str__(self):
        return self.display


class C(models.Model):
    display = models.CharField(max_length=150)
    b = models.ForeignKey(B, on_delete=models.CASCADE)

    def __str__(self):
        return self.display


class D(models.Model):
    display = models.CharField(max_length=150)
    c = models.ForeignKey(C, on_delete=models.CASCADE)

    def __str__(self):
        return self.display


class E(models.Model):
    display = models.CharField(max_length=150)
    d = models.ForeignKey(D, on_delete=models.CASCADE)

    def __str__(self):
        return self.display


class ABCDE(models.Model):
    a = models.ManyToManyField(A)
    b = models.ForeignKey(B, on_delete=models.CASCADE)
    c = models.ManyToManyField(C)
    d = models.ForeignKey(D, on_delete=models.CASCADE)
    e = models.ManyToManyField(E)

    def __str__(self):
        return ' '.join([x.display for x in self.e.all()])


def validate_inputs(value):
    if value.find('_') != -1:
        raise ValidationError(
            _('%(value)s need more digits'),
            params={'value': value},
        )


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
    serial_number = models.CharField(max_length=23, validators=[validate_inputs])
    taxid = models.CharField(max_length=11, validators=[validate_inputs])
    credit_card = models.CharField(max_length=19, validators=[validate_credit_card])
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
    # blank=True on purpose: FileChunkedUpload ships a "delete this file"
    # checkbox, and on a field that does not allow blank the only thing that
    # checkbox can produce is "this field cannot be blank" on submit.
    fileexample = models.FileField(upload_to='filedemo', blank=True)


class Calendar(models.Model):
    title = models.CharField(max_length=255)
    options = models.JSONField(null=True, blank=True)
    events = models.JSONField(null=True, blank=True)


class Event(models.Model):
    calendar = models.ForeignKey(to=Calendar, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, null=True, blank=True)
    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)
    color = models.CharField(max_length=20, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.title


class ObjectManagerDemoModel(models.Model):
    ELEMENTS = (
        (1, 'A'),
        (2, 'B'),
        (3, 'C'),
        (4, 'D'),
    )
    name = models.CharField(max_length=150)
    float_number = models.FloatField(default=0)
    knob_number = models.IntegerField(default=0)
    born_date = models.DateField()
    last_time = models.DateTimeField()
    livetime_range = models.CharField(max_length=256)  # daterange field
    description = models.TextField()  # wysiwyg
    simple_archive = models.FileField(upload_to='files')
    chunked_archive = models.FileField(upload_to='chunked_files')
    radio_elements = models.IntegerField(choices=ELEMENTS)
    taging_list = models.CharField(max_length=256)
    yes_no = models.BooleanField(default=False)

    field_autocomplete = models.ForeignKey(
        Country, related_name='ct', on_delete=models.CASCADE
    )
    m2m_autocomplete = models.ManyToManyField(Country, related_name='autocomplext')
    field_select = models.ForeignKey('Community', on_delete=models.CASCADE)
    m2m_multipleselect = models.ManyToManyField(A)

    def __str__(self):
        return self.name


class ObjectManagerDemoNote(models.Model):
    """Child of ObjectManagerDemoModel, managed with BaseInlineObjectManagement."""

    demo_object = models.ForeignKey(
        ObjectManagerDemoModel, related_name='notes', on_delete=models.CASCADE
    )
    title = models.CharField(max_length=150)
    body = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class DigitalSignature(models.Model):
    file_code = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(max_length=50, null=True, blank=True)
    file = models.FileField(upload_to='digital_signature/')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        #  add name to filename
        if not self.filename and self.file:
            self.filename = self.file.name.split('/')[-1]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.filename or str(self.file_code)


class PDFDocument(models.Model):
    name = models.CharField(max_length=255)
    pdf_file = models.FileField(upload_to='pdfdocuments/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'PDF Document'
        verbose_name_plural = 'PDF Documents'


class SelectImage(models.Model):
    name = models.CharField(max_length=255)
    img = models.FileField(upload_to='images', null=True, blank=True)

    def __str__(self):
        return (
            '<span><img style="width: 2em; height: 2em;" src="'
            + self.img.url
            + '">'
            + self.name
            + '</span>'
        )


class Img(models.Model):
    multi_image = models.ManyToManyField(
        SelectImage, blank=True, related_name='imges_x'
    )
    related_name = models.ForeignKey(
        SelectImage,
        blank=True,
        null=True,
        related_name='related_img',
        on_delete=models.CASCADE,
    )
    # Same select2-with-images widget as the two fields above, pointed at a
    # different source of pictures: SelectImage serves an uploaded FileField,
    # CountryFlagLookup serves the flags view.
    country = models.ForeignKey(
        Country,
        blank=True,
        null=True,
        related_name='img_country',
        on_delete=models.CASCADE,
    )
    countries = models.ManyToManyField(
        Country, blank=True, related_name='img_countries'
    )

    def __str__(self):
        return 'Imgs %d' % (self.multi_image.count())


# Trash
class Customer(DeletedWithTrash):
    name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=150)
    email = models.EmailField()

    def __str__(self):
        return self.name

    def delete(
        self, using=None, keep_parents=False, *, hard=False, user=None, **kwargs
    ):

        if self.is_deleted and not hard:
            return

        result = super().delete(
            using=using, keep_parents=keep_parents, hard=hard, user=user, **kwargs
        )

        return result


# Maps
class Place(models.Model):
    name = models.CharField(max_length=150)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    # based_fields geocodes from the two fields above when the point is empty.
    location = GTPointField(
        zoom=8,
        center=(9.9327, -84.0875),
        search=True,
        based_fields=['#id_country', '#id_city'],
        blank=True,
    )

    def __str__(self):
        return self.name


# PositionsGrid
class Warehouse(models.Model):
    """A storage wall drawn as rows of cells.

    The shape is stored, not derived from the boxes: a cell may be empty, and
    rows are irregular on purpose -- ``[2, 4, 3, 4]`` is four rows of two,
    four, three and four cells, which is what a real wall of shelving looks
    like.
    """

    name = models.CharField(max_length=150)
    shape = models.JSONField(default=list, blank=True)

    def __str__(self):
        return self.name


class WarehouseBox(models.Model):
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name='boxes'
    )
    code = models.CharField(max_length=50)
    content = models.CharField(max_length=150, blank=True, default='')
    quantity = models.PositiveIntegerField(default=0)
    row = models.PositiveSmallIntegerField(default=0)
    col = models.PositiveSmallIntegerField(default=0)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['row', 'col', 'order', 'pk']

    def __str__(self):
        return self.code


class UUIDThing(models.Model):
    """A model keyed by a UUID: the flow tests use it for non-integer pks."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


# -- the flow demos (demoapp/gtflows.py) ---------------------------------------
class PurchaseRequest(models.Model):
    title = models.CharField(_('What'), max_length=150)
    amount = models.DecimalField(_('Amount'), max_digits=12, decimal_places=2)
    justification = models.TextField(_('Justification'), blank=True, default='')
    supplier = models.CharField(_('Supplier'), max_length=150, blank=True, default='')
    requester = models.ForeignKey(User, on_delete=models.CASCADE,
                                  related_name='demo_purchases',
                                  verbose_name=_('Requester'))
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class SupportTicket(models.Model):
    PRIORITIES = [('low', _('Low')), ('normal', _('Normal')), ('high', _('High'))]

    subject = models.CharField(_('Subject'), max_length=150)
    description = models.TextField(_('Description'))
    priority = models.CharField(_('Priority'), max_length=10, choices=PRIORITIES,
                                default='normal')
    resolution = models.TextField(_('Resolution'), blank=True, default='')
    reporter = models.ForeignKey(User, on_delete=models.CASCADE,
                                 related_name='demo_tickets',
                                 verbose_name=_('Reporter'))
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.subject


class EditorialDocument(models.Model):
    title = models.CharField(_('Title'), max_length=150)
    body = models.TextField(_('Text'))
    reviewer_notes = models.TextField(_('Reviewer notes'), blank=True, default='')
    published_at = models.DateTimeField(_('Published'), null=True, blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE,
                               related_name='demo_documents',
                               verbose_name=_('Author'))

    class Meta:
        permissions = [('review_editorialdocument', 'Can review documents')]

    def __str__(self):
        return self.title


class LeaveRequest(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE,
                                 related_name='demo_leaves',
                                 verbose_name=_('Employee'))
    approver = models.ForeignKey(User, on_delete=models.CASCADE,
                                 related_name='demo_leaves_to_approve',
                                 verbose_name=_('Approver'))
    start = models.DateField(_('From'))
    end = models.DateField(_('To'))
    reason = models.CharField(_('Reason'), max_length=200, blank=True, default='')

    def __str__(self):
        return '%s: %s - %s' % (self.employee, self.start, self.end)


class ExpenseReport(models.Model):
    """The expense approval demo: the same flow declared in Python
    (``demoapp.ExpenseFlow``) and in JSON (``demoapp.expenses_json``)."""

    FLOWS = [('demoapp.ExpenseFlow', _('Python')),
             ('demoapp.expenses_json', _('JSON'))]

    title = models.CharField(_('What'), max_length=150)
    amount = models.DecimalField(_('Amount'), max_digits=12, decimal_places=2)
    requester = models.ForeignKey(User, on_delete=models.CASCADE,
                                  related_name='demo_expenses',
                                  verbose_name=_('Requester'))
    manager = models.ForeignKey(User, on_delete=models.CASCADE,
                                related_name='demo_expenses_to_approve',
                                verbose_name=_('Manager'))
    #: Which of the two equivalent flows it goes through.
    flow_name = models.CharField(max_length=50, choices=FLOWS,
                                 default='demoapp.ExpenseFlow')
    paid = models.BooleanField(_('Paid'), default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return '%s (%s)' % (self.title, self.amount)


class DynamicContact(models.Model):
    """Dynamic actions and cascading LOVs demo (/dynamic_actions/).

    country, province and canton hold codes of the LOVs in demoapp/gtlovs.py.
    """

    KINDS = (('person', _('Person')), ('company', _('Company')))

    kind = models.CharField(_('Kind'), max_length=10, choices=KINDS,
                            default='person')
    name = models.CharField(_('Name'), max_length=150)
    company_name = models.CharField(_('Company name'), max_length=150, blank=True,
                                    default='')
    company_id = models.CharField(_('Company id'), max_length=30, blank=True,
                                  default='')
    country = models.CharField(_('Country'), max_length=10)
    province = models.CharField(_('Province'), max_length=10, blank=True,
                                default='')
    canton = models.CharField(_('Canton'), max_length=10, blank=True, default='')
    quantity = models.PositiveIntegerField(_('Quantity'), default=1)
    price = models.DecimalField(_('Price'), max_digits=12, decimal_places=2,
                                default=0)
    discount = models.DecimalField(_('Discount %'), max_digits=5, decimal_places=2,
                                   default=0)
    total = models.DecimalField(_('Total'), max_digits=14, decimal_places=2,
                                default=0)

    def __str__(self):
        return self.name


# -- the catalogue of the design demos (demoapp/gtdesign/, djgentelella.designs) --
class ProductCategory(models.Model):
    name = models.CharField(_('Name'), max_length=100)
    description = models.CharField(_('Description'), max_length=250, blank=True,
                                   default='')

    class Meta:
        verbose_name = _('category')
        verbose_name_plural = _('categories')
        ordering = ['name']

    def __str__(self):
        return self.name


class ProductTag(models.Model):
    name = models.CharField(_('Name'), max_length=50)

    class Meta:
        verbose_name = _('tag')
        verbose_name_plural = _('tags')
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    STATUS = (('draft', _('Draft')), ('active', _('Active')),
              ('retired', _('Retired')))

    name = models.CharField(_('Name'), max_length=150)
    description = models.TextField(_('Description'), blank=True, default='')
    price = models.DecimalField(_('Price'), max_digits=10, decimal_places=2)
    available_since = models.DateField(_('Available since'), null=True, blank=True)
    status = models.CharField(_('Status'), max_length=20, choices=STATUS,
                              default='draft')
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='products',
                                 verbose_name=_('Category'))
    tags = models.ManyToManyField(ProductTag, blank=True, related_name='products',
                                  verbose_name=_('Tags'))
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                              blank=True, related_name='demo_products',
                              verbose_name=_('Owner'))

    class Meta:
        verbose_name = _('product')
        verbose_name_plural = _('products')

    def __str__(self):
        return self.name


class AlertRule(AbstractAlertRule):
    """The demo's alert rules: who to notify is a list of users."""

    notify_users = models.ManyToManyField(User, blank=True, related_name='+',
                                          verbose_name=_('Notify'))

    def get_recipients(self, obj=None, context=None):
        return list(self.notify_users.all()) + super().get_recipients(obj, context)


class AlertEvent(AbstractAlertEvent):
    rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE,
                             related_name='events', verbose_name=_('Alert rule'))

    class Meta(AbstractAlertEvent.Meta):
        pass


class Equipment(models.Model):
    """A piece of lab equipment with a calibration that comes due."""

    name = models.CharField(max_length=150, verbose_name=_('Name'))
    next_calibration = models.DateField(null=True, blank=True,
                                        verbose_name=_('Next calibration'))
    alerts = GenericRelation(AlertEvent, related_query_name='equipment')

    def __str__(self):
        return self.name


class Calibration(models.Model):
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE,
                                  related_name='calibrations')
    done = models.DateField(verbose_name=_('Done'))

    def __str__(self):
        return '%s %s' % (self.equipment, self.done)


class Meetup(models.Model):
    """A community meetup: the rows of the region components (cards,
    calendar and map) of ``/designs/meetups/``. ``site`` empty is global."""

    KINDS = (('talk', 'Talk'), ('workshop', 'Workshop'), ('social', 'Social'))

    title = models.CharField(max_length=150)
    kind = models.CharField(max_length=20, choices=KINDS, default='talk')
    city = models.CharField(max_length=100, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    location = GTPointField(blank=True)
    picture = models.URLField(blank=True)
    site = models.ForeignKey('sites.Site', null=True, blank=True,
                             on_delete=models.CASCADE)

    def __str__(self):
        return self.title


class WidgetShowcase(models.Model):
    """The form widgets of the catalog (/formwidgets/): one field per widget.

    ``product`` holds a code of the ``demo_products`` LOV (demoapp/gtlovs.py),
    ``budget_min``/``budget_max`` the pair of the range pair field.
    """

    name = models.CharField(_('Name'), max_length=150)
    rating = models.PositiveSmallIntegerField(_('Rating'), default=0)
    active = models.BooleanField(_('Active'), default=True)
    volume = models.IntegerField(_('Volume'), default=50)
    budget_min = models.IntegerField(_('Minimum budget'), null=True, blank=True)
    budget_max = models.IntegerField(_('Maximum budget'), null=True, blank=True)
    category = models.CharField(_('Category'), max_length=60, blank=True)
    product = models.CharField(_('Product'), max_length=20, blank=True)
    description = models.TextField(_('Description'), blank=True)
    photo = models.ImageField(_('Photo'), upload_to='showcase/', null=True,
                              blank=True)
    code = models.CharField(_('Code'), max_length=200, blank=True)
    address = models.CharField(_('Address'), max_length=250, blank=True)
    location = GTPointField(blank=True)

    def __str__(self):
        return self.name


class Department(models.Model):
    """A unit of an organization chart: the rows of the ``tree`` component of
    ``/designs/insights/``. ``parent`` empty is a root, ``site`` empty is
    global."""

    name = models.CharField(max_length=150)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='units',
                               on_delete=models.SET_NULL)
    icon = models.CharField(max_length=60, blank=True)
    head = models.CharField(max_length=150, blank=True)
    site = models.ForeignKey('sites.Site', null=True, blank=True,
                             on_delete=models.CASCADE)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
