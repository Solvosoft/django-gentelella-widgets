from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ..models import Warehouse, WarehouseBox
from .serializer import (
    BoxSerializer,
    ColSerializer,
    CreateBoxSerializer,
    MoveBoxSerializer,
    RowSerializer,
    WarehouseBoxSerializer,
)


class WarehouseViewSet(viewsets.GenericViewSet):
    """The seven handlers PositionsGrid needs, plus the initial state.

    Every endpoint answers with the **whole** new state, so from the client's
    point of view the seven are interchangeable: it calls one and repaints with
    what comes back. Nothing is ever patched locally.

    The destructive ones answer 400 when the row or column still holds boxes.
    That is the point of the demo: it is the only way to see on screen that a
    rejected handler repaints nothing and fires ``pg:error``.
    """

    queryset = Warehouse.objects.all()
    serializer_class = WarehouseBoxSerializer

    def build_state(self, warehouse):
        boxes = list(warehouse.boxes.all())
        cells = [[[] for _ in range(width)] for width in warehouse.shape]
        for box in boxes:
            if box.row < len(cells) and box.col < len(cells[box.row]):
                cells[box.row][box.col].append(box.pk)
        items = {
            str(box.pk): WarehouseBoxSerializer(box).data for box in boxes
        }
        return {'data': {'cells': cells}, 'items': items}

    def state_response(self, warehouse):
        return Response(self.build_state(warehouse))

    def validated(self, request, serializer_class):
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def rejected(self, detail):
        return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def state(self, request, pk=None):
        return self.state_response(self.get_object())

    @action(detail=True, methods=['post'])
    def add_row(self, request, pk=None):
        warehouse = self.get_object()
        # As wide as the last row, so a warehouse that is already ragged stays
        # ragged instead of being squared off by the act of growing.
        width = warehouse.shape[-1] if warehouse.shape else 1
        warehouse.shape = list(warehouse.shape) + [width]
        warehouse.save()
        return self.state_response(warehouse)

    @action(detail=True, methods=['post'])
    def remove_row(self, request, pk=None):
        warehouse = self.get_object()
        data = self.validated(request, RowSerializer)
        row = data['row']
        if row >= len(warehouse.shape):
            return self.rejected('The row does not exist')
        if warehouse.boxes.filter(row=row).exists():
            return self.rejected('The row still contains boxes')
        shape = list(warehouse.shape)
        del shape[row]
        with transaction.atomic():
            warehouse.shape = shape
            warehouse.save()
            for box in warehouse.boxes.filter(row__gt=row):
                box.row -= 1
                box.save()
        return self.state_response(warehouse)

    @action(detail=True, methods=['post'])
    def add_col(self, request, pk=None):
        warehouse = self.get_object()
        # One cell to every row: each row grows by one, so the relative
        # irregularity is preserved instead of being flattened.
        warehouse.shape = [width + 1 for width in warehouse.shape] or [1]
        warehouse.save()
        return self.state_response(warehouse)

    @action(detail=True, methods=['post'])
    def remove_col(self, request, pk=None):
        warehouse = self.get_object()
        data = self.validated(request, ColSerializer)
        col = data['col']
        if not any(width > col for width in warehouse.shape):
            return self.rejected('The column does not exist')
        if warehouse.boxes.filter(col=col).exists():
            return self.rejected('The column still contains boxes')
        # Only the rows that actually have that column shrink; the shorter ones
        # are left alone, which is what keeps the shape the user drew.
        shape = [w - 1 if w > col else w for w in warehouse.shape]
        with transaction.atomic():
            warehouse.shape = shape
            warehouse.save()
            for box in warehouse.boxes.filter(col__gt=col):
                box.col -= 1
                box.save()
        return self.state_response(warehouse)

    @action(detail=True, methods=['post'])
    def create_item(self, request, pk=None):
        warehouse = self.get_object()
        data = self.validated(request, CreateBoxSerializer)
        if not self.fits(warehouse, data['row'], data['col']):
            return self.rejected('That cell is not part of the warehouse')
        count = warehouse.boxes.count() + 1
        WarehouseBox.objects.create(
            warehouse=warehouse,
            code=data.get('code') or 'BOX-%03d' % count,
            content=data.get('content', ''),
            quantity=data.get('quantity', 0),
            row=data['row'],
            col=data['col'],
        )
        return self.state_response(warehouse)

    @action(detail=True, methods=['post'])
    def move_item(self, request, pk=None):
        warehouse = self.get_object()
        data = self.validated(request, MoveBoxSerializer)
        if not self.fits(warehouse, data['row'], data['col']):
            return self.rejected('That cell is not part of the warehouse')
        box = warehouse.boxes.filter(pk=data['id']).first()
        if box is None:
            return self.rejected('That box is not in this warehouse')
        box.row, box.col = data['row'], data['col']
        box.save()
        return self.state_response(warehouse)

    @action(detail=True, methods=['post'])
    def remove_item(self, request, pk=None):
        warehouse = self.get_object()
        data = self.validated(request, BoxSerializer)
        box = warehouse.boxes.filter(pk=data['id']).first()
        if box is None:
            return self.rejected('That box is not in this warehouse')
        box.delete()
        return self.state_response(warehouse)

    def fits(self, warehouse, row, col):
        return row < len(warehouse.shape) and col < warehouse.shape[row]
