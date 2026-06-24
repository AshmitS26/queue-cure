import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from clinic import db


class QueueConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.clinic_id = self.scope['url_route']['kwargs']['clinic_id']
        self.doctor_id = self.scope['url_route']['kwargs']['doctor_id']
        self.group_name = f'clinic_{self.clinic_id}_{self.doctor_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        snapshot = await sync_to_async(self._snapshot)()
        await self.send(text_data=json.dumps(snapshot))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def queue_update(self, event):
        await self.send(text_data=json.dumps(event))

    def _snapshot(self):
        queue = db.get_queue(self.clinic_id, self.doctor_id)
        current = db.get_current_called(self.clinic_id, self.doctor_id)
        doctor = db.get_doctor(self.doctor_id) or {}
        return {
            'type': 'queue_update',
            'doctor_id': self.doctor_id,
            'current_called': self._ser(current),
            'queue': [self._ser(t) for t in queue],
            'queue_length': len(queue),
            'ema_avg': doctor.get('ema_avg', 10),
        }

    @staticmethod
    def _ser(token):
        if not token:
            return None
        return {
            'token_id': token['token_id'],
            'patient_name': token['patient_name'],
            'phone': token.get('phone', ''),
            'status': token['status'],
            'clinic_id': token['clinic_id'],
            'doctor_id': token['doctor_id'],
            'check_in_time': token['check_in_time'].isoformat() if token.get('check_in_time') else None,
            'called_at': token['called_at'].isoformat() if token.get('called_at') else None,
        }


class LiveBoardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.clinic_id = self.scope['url_route']['kwargs']['clinic_id']
        self.group_name = f'liveboard_{self.clinic_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        board = await sync_to_async(self._snapshot)()
        await self.send(text_data=json.dumps({'type': 'liveboard_update', 'board': board}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def liveboard_update(self, event):
        await self.send(text_data=json.dumps(event))

    def _snapshot(self):
        from clinic.views import _build_live_board
        return _build_live_board(self.clinic_id)
