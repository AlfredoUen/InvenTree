"""
JSON API for the Stock app
"""

from django_filters.rest_framework import FilterSet, DjangoFilterBackend
from django_filters import NumberFilter

from django.conf.urls import url, include
from django.urls import reverse

from .models import StockLocation, StockItem
from .models import StockItemTracking

from part.models import PartCategory

from .serializers import StockItemSerializer, StockQuantitySerializer
from .serializers import LocationSerializer
from .serializers import StockTrackingSerializer

from InvenTree.views import TreeSerializer

from rest_framework.serializers import ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics, response, filters, permissions


class StockCategoryTree(TreeSerializer):
    title = 'Stock'
    model = StockLocation

    @property
    def root_url(self):
        return reverse('stock-index')


class StockDetail(generics.RetrieveUpdateDestroyAPIView):
    """ API detail endpoint for Stock object

    get:
    Return a single StockItem object

    post:
    Update a StockItem

    delete:
    Remove a StockItem
    """

    queryset = StockItem.objects.all()
    serializer_class = StockItemSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)


class StockFilter(FilterSet):
    """ FilterSet for advanced stock filtering.

    Allows greater-than / less-than filtering for stock quantity
    """

    min_stock = NumberFilter(name='quantity', lookup_expr='gte')
    max_stock = NumberFilter(name='quantity', lookup_expr='lte')

    class Meta:
        model = StockItem
        fields = ['quantity', 'part', 'location']


class StockStocktake(APIView):
    """ Stocktake API endpoint provides stock update of multiple items simultaneously.
    The 'action' field tells the type of stock action to perform:
    - stocktake: Count the stock item(s)
    - remove: Remove the quantity provided from stock
    - add: Add the quantity provided from stock
    """

    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly,
    ]

    def post(self, request, *args, **kwargs):

        if 'action' not in request.data:
            raise ValidationError({'action': 'Stocktake action must be provided'})

        action = request.data['action']

        ACTIONS = ['stocktake', 'remove', 'add']

        if action not in ACTIONS:
            raise ValidationError({'action': 'Action must be one of ' + ','.join(ACTIONS)})

        elif 'items[]' not in request.data:
            raise ValidationError({'items[]:' 'Request must contain list of items'})

        items = []

        # Ensure each entry is valid
        for entry in request.data['items[]']:
            if 'pk' not in entry:
                raise ValidationError({'pk': 'Each entry must contain pk field'})
            elif 'quantity' not in entry:
                raise ValidationError({'quantity': 'Each entry must contain quantity field'})

            item = {}
            try:
                item['item'] = StockItem.objects.get(pk=entry['pk'])
            except StockItem.DoesNotExist:
                raise ValidationError({'pk': 'No matching StockItem found for pk={pk}'.format(pk=entry['pk'])})
            try:
                item['quantity'] = int(entry['quantity'])
            except ValueError:
                raise ValidationError({'quantity': 'Quantity must be an integer'})

            if item['quantity'] < 0:
                raise ValidationError({'quantity': 'Quantity must be >= 0'})

            items.append(item)

        # Stocktake notes
        notes = ''

        if 'notes' in request.data:
            notes = request.data['notes']

        n = 0

        for item in items:
            quantity = int(item['quantity'])

            if action == u'stocktake':
                if item['item'].stocktake(quantity, request.user, notes=notes):
                    n += 1
            elif action == u'remove':
                if item['item'].take_stock(quantity, request.user, notes=notes):
                    n += 1
            elif action == u'add':
                if item['item'].add_stock(quantity, request.user, notes=notes):
                    n += 1

        return Response({'success': 'Updated stock for {n} items'.format(n=n)})


class StockMove(APIView):
    """ API endpoint for performing stock movements """

    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly,
    ]

    def post(self, request, *args, **kwargs):

        data = request.data

        if 'location' not in data:
            raise ValidationError({'location': 'Destination must be specified'})

        try:
            loc_id = int(data.get('location'))
        except ValueError:
            raise ValidationError({'location': 'Integer ID required'})

        try:
            location = StockLocation.objects.get(pk=loc_id)
        except StockLocation.DoesNotExist:
            raise ValidationError({'location': 'Location does not exist'})

        if 'stock' not in data:
            raise ValidationError({'stock': 'Stock list must be specified'})
        
        stock_list = data.get('stock')

        if type(stock_list) is not list:
            raise ValidationError({'stock': 'Stock must be supplied as a list'})

        if 'notes' not in data:
            raise ValidationError({'notes': 'Notes field must be supplied'})

        for item in stock_list:
            try:
                stock_id = int(item['pk'])
                if 'quantity' in item:
                    quantity = int(item['quantity'])
                else:
                    # If quantity not supplied, we'll move the entire stock
                    quantity = None
            except ValueError:
                # Ignore this one
                continue

            # Ignore a zero quantity movement
            if quantity <= 0:
                continue

            try:
                stock = StockItem.objects.get(pk=stock_id)
            except StockItem.DoesNotExist:
                continue

            if quantity is None:
                quantity = stock.quantity

            stock.move(location, data.get('notes'), request.user, quantity=quantity)

        return Response({'success': 'Moved parts to {loc}'.format(
            loc=str(location)
        )})


class StockLocationList(generics.ListCreateAPIView):
    """ API endpoint for list view of StockLocation objects:

    - GET: Return list of StockLocation objects
    - POST: Create a new StockLocation
    """

    queryset = StockLocation.objects.all()

    serializer_class = LocationSerializer

    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly,
    ]

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    filter_fields = [
        'parent',
    ]


class StockList(generics.ListCreateAPIView):
    """ API endpoint for list view of Stock objects

    - GET: Return a list of all StockItem objects (with optional query filters)
    - POST: Create a new StockItem

    Additional query parameters are available:
        - location: Filter stock by location
        - category: Filter by parts belonging to a certain category
    """

    def get_queryset(self):
        """
        If the query includes a particular location,
        we may wish to also request stock items from all child locations.
        """

        # Does the client wish to filter by stock location?
        loc_id = self.request.query_params.get('location', None)

        # Start with all objects
        stock_list = StockItem.objects.all()

        if loc_id:
            try:
                location = StockLocation.objects.get(pk=loc_id)
                stock_list = stock_list.filter(location__in=location.getUniqueChildren())
                 
            except StockLocation.DoesNotExist:
                pass

        # Does the client wish to filter by part category?
        cat_id = self.request.query_params.get('category', None)

        if cat_id:
            try:
                category = PartCategory.objects.get(pk=cat_id)
                stock_list = stock_list.filter(part__category__in=category.getUniqueChildren())

            except PartCategory.DoesNotExist:
                pass

        return stock_list

    serializer_class = StockItemSerializer

    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly,
    ]

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    filter_fields = [
        'part',
        'supplier_part',
        'customer',
        'belongs_to',
        # 'status' TODO - There are some issues filtering based on an enumeration field
    ]


class StockStocktakeEndpoint(generics.UpdateAPIView):
    """ API endpoint for performing stocktake """

    queryset = StockItem.objects.all()
    serializer_class = StockQuantitySerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def update(self, request, *args, **kwargs):
        object = self.get_object()
        object.stocktake(request.data['quantity'], request.user)

        serializer = self.get_serializer(object)

        return response.Response(serializer.data)


class StockTrackingList(generics.ListCreateAPIView):
    """ API endpoint for list view of StockItemTracking objects.

    StockItemTracking objects are read-only
    (they are created by internal model functionality)

    - GET: Return list of StockItemTracking objects
    """

    queryset = StockItemTracking.objects.all()
    serializer_class = StockTrackingSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    filter_fields = [
        'item',
        'user',
    ]

    ordering = '-date'

    ordering_fields = [
        'date',
    ]

    search_fields = [
        'title',
        'notes',
    ]


class LocationDetail(generics.RetrieveUpdateDestroyAPIView):
    """ API endpoint for detail view of StockLocation object

    - GET: Return a single StockLocation object
    - PATCH: Update a StockLocation object
    - DELETE: Remove a StockLocation object
    """

    queryset = StockLocation.objects.all()
    serializer_class = LocationSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)


stock_endpoints = [
    url(r'^$', StockDetail.as_view(), name='api-stock-detail'),
]

location_endpoints = [
    url(r'^$', LocationDetail.as_view(), name='api-location-detail'),
]

stock_api_urls = [
    url(r'location/?', StockLocationList.as_view(), name='api-location-list'),

    url(r'location/(?P<pk>\d+)/', include(location_endpoints)),

    url(r'stocktake/?', StockStocktake.as_view(), name='api-stock-stocktake'),

    url(r'move/?', StockMove.as_view(), name='api-stock-move'),

    url(r'track/?', StockTrackingList.as_view(), name='api-stock-track'),

    url(r'^tree/?', StockCategoryTree.as_view(), name='api-stock-tree'),

    # Detail for a single stock item
    url(r'^(?P<pk>\d+)/', include(stock_endpoints)),

    url(r'^.*$', StockList.as_view(), name='api-stock-list'),
]
