import json
import os
from datetime import datetime
from typing import Dict, List


class DebtStorage:
    def __init__(self, file_path='data/debts.json'):
        self.file_path = file_path
        self.data: Dict[str, Dict] = {}
        self._ensure_path()
        self._load()

    def _ensure_path(self):
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)

    def _load(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        except (IOError, json.JSONDecodeError):
            self.data = {}

    def _save(self):
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get_people(self) -> List[str]:
        return list(self.data.keys())

    def add_person(self, name: str):
        if name not in self.data:
            self.data[name] = {'operations': [], 'total': 0}
            self._save()

    def add_operation(self, name: str, amount: int, reason: str = ''):
        now = datetime.now().isoformat()
        op = {'amount': amount, 'reason': reason, 'timestamp': now}
        self.data[name]['operations'].append(op)
        self.data[name]['total'] += amount
        self._save()

    def get_total(self, name: str) -> int:
        return self.data.get(name, {}).get('total', 0)

    def get_operations(self, name: str) -> List[Dict]:
        return self.data.get(name, {}).get('operations', [])

    def remove_operation(self, name: str, index: int):
        if name in self.data and 0 <= index < len(self.data[name]['operations']):
            amount = self.data[name]['operations'][index]['amount']
            del self.data[name]['operations'][index]
            self.data[name]['total'] -= amount
            self._save()

storage = DebtStorage()
