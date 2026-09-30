"""Sensors showing the state of the MeDaCo statistics import."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import EntityCategory, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MedacoConfigEntry
from .const import DOMAIN, OBIS_NAMES
from .coordinator import MedacoCoordinator, RegisterState


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MedacoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for statistic_id in coordinator.data:
        entities.append(MedacoTotalSensor(coordinator, statistic_id))
        entities.append(MedacoLastDataSensor(coordinator, statistic_id))
    async_add_entities(entities)


class _MedacoEntity(CoordinatorEntity[MedacoCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: MedacoCoordinator, statistic_id: str) -> None:
        super().__init__(coordinator)
        self._statistic_id = statistic_id
        point = self._register.metering_point
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, point.id)},
            name=point.name,
            manufacturer="Westnetz",
            model="Intelligentes Messsystem",
        )

    @property
    def _register(self) -> RegisterState:
        return self.coordinator.data[self._statistic_id]

    @property
    def available(self) -> bool:
        return super().available and self._statistic_id in self.coordinator.data


class MedacoTotalSensor(_MedacoEntity):
    """Imported meter total. Use the statistic, not this sensor, for Energy."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: MedacoCoordinator, statistic_id: str) -> None:
        super().__init__(coordinator, statistic_id)
        obis = self._register.line.obis
        self._attr_unique_id = f"{statistic_id}_total"
        self._attr_name = f"{OBIS_NAMES.get(obis, obis)} importiert"

    @property
    def native_value(self) -> float | None:
        return self._register.total_kwh


class MedacoLastDataSensor(_MedacoEntity):
    """Start of the newest hour the portal has delivered."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: MedacoCoordinator, statistic_id: str) -> None:
        super().__init__(coordinator, statistic_id)
        obis = self._register.line.obis
        self._attr_unique_id = f"{statistic_id}_last_data"
        self._attr_name = f"{OBIS_NAMES.get(obis, obis)} Datenstand"

    @property
    def native_value(self):
        return self._register.last_hour
