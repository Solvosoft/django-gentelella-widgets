===============
Pallete widget
===============

It is a kind of helper, that is located at bottom left had side corner, with a mail icon.
This widget is used to add description for each input field in the different displayed forms of the views.
When we hit the mail icon the helper modal is displayed.

.. image:: https://user-images.githubusercontent.com/20632410/84224020-b95f4180-aa98-11ea-97a3-947fc465053c.png


The help button appears at the left side of the label in each input field as question mark,
when we hit the show button in the helper modal.

.. image:: https://user-images.githubusercontent.com/20632410/84223921-77360000-aa98-11ea-9710-a5c3ce66c07e.png

How to implement it ??

The custom command 'createdemo' of the demo WEB site create this widget with the following code:

.. code:: python

   item = MenuItem.objects.create(
       parent = None,
       title = '',
       url_name ='djgentelella.menu_widgets.palette.PalleteWidget',
       category = 'sidebarfooter',
       is_reversed = False,
       reversed_kwargs = None,
       reversed_args = None,
       is_widget = True,
       icon = 'fa fa-envelope-o',
       only_icon = True
   )



