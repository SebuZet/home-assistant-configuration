import os, tempfile
from io import BytesIO
import logging
import json
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_VALUE_TEMPLATE, CONF_NAME, CONF_UNIT_OF_MEASUREMENT)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pysmb>=1.1.27']

CONF_AVNODE_IP = 'avnode_ip'
CONF_AVNODE_USER = 'avnode_user'
CONF_AVNODE_PASS = 'avnode_pass'
CONF_AVNODE_FILE = 'avnode_file'
CONF_NAME = 'name'
DEFAULT_FILE = 'latest_config_measurements.json'
DEFAULT_USER = 'airvisual'
DEFAULT_NAME = 'AirVisualPro'
ICON = 'mdi:file'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
  vol.Required(CONF_AVNODE_IP): cv.string,
  vol.Required(CONF_AVNODE_PASS): cv.string,
  vol.Optional(CONF_AVNODE_USER, default=DEFAULT_USER): cv.string,
  vol.Optional(CONF_AVNODE_FILE, default=DEFAULT_FILE): cv.string,
  vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
  vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
  vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
})

async def async_setup_platform(hass, config, async_add_entities,
                             discovery_info=None):
  """Set up the file sensor."""
  file_path = config.get(CONF_AVNODE_FILE)
  name = config.get(CONF_NAME)
  unit = config.get(CONF_UNIT_OF_MEASUREMENT)
  value_template = config.get(CONF_VALUE_TEMPLATE)

  ip = config.get(CONF_AVNODE_IP)
  user = config.get(CONF_AVNODE_USER)
  pwd = config.get(CONF_AVNODE_PASS)

  if value_template is not None:
    value_template.hass = hass

  async_add_entities(
    [AirVisualProSensor(name, ip, user, pwd, file_path, unit, value_template)], True)

class AirVisualProSensor(Entity):
  """Implementation of a AirVisualPro sensor."""

  def __init__(self, name, ip, username, password, file_path, unit_of_measurement, value_template):
    """Initialize the file sensor."""
    self._name = name
    self._file_path = file_path
    self._username = username
    self._password = password
    self._ip = ip
    self._unit_of_measurement = unit_of_measurement
    self._val_tpl = value_template
    self._attributes = None
    self._state = 'off'

  def connect(self):
    from smb.SMBConnection import SMBConnection
    from smb.smb2_constants import SMB2_DIALECT_2
    from smb import smb_structs

    conn = SMBConnection(self._username, self._password, 'hass', '', use_ntlm_v2 = True)
    try:
        conn.connect(self._ip, 139) #139=NetBIOS / 445=TCP
    except (Exception):
        _LOGGER.warning("Problem with connecting to AirVisualPro device!!! ")
        self._state = 'off'
    return conn

  def getServiceName(self, conn):
    shares = conn.listShares()
    for s in shares:
      if s.type == 0:  # 0 = DISK_TREE
        return s.name        
    return ''

  def download(self):
    conn = self.connect()
    if conn:
      service_name = self.getServiceName(conn)
      attr = conn.getAttributes(service_name, '\\'+ self._file_path)
      file_obj = BytesIO()
      file_attributes, filesize = conn.retrieveFile(service_name, '\\'+ self._file_path, file_obj)
      file_obj.seek(0)
      data = file_obj.read(50*1024)
      conn.close()
      file_obj.close()
      return data.decode('UTF-8')
    return ""

  @property
  def name(self):
    """Return the name of the sensor."""
    return self._name

  @property
  def unit_of_measurement(self):
    """Return the unit the value is expressed in."""
    return self._unit_of_measurement

  @property
  def icon(self):
    """Return the icon to use in the frontend, if any."""
    return ICON

  @property
  def device_state_attributes(self):
    """Return the state attributes."""
    return self._attributes

  @property
  def state(self):
    """Return the state of the sensor."""
    return self._state

  def update(self):
    self._state = 'off'
    value = self.download().strip()

    self._attributes = {}
    if value:
      try:
        json_dict = json.loads(self.download().strip())
        if isinstance(json_dict, dict):
          self._attributes = json_dict
        else:
          _LOGGER.warning("JSON result was not a dictionary")
      except ValueError:
        _LOGGER.warning("REST result could not be parsed as JSON")
        _LOGGER.debug("Erroneous JSON: %s", value)
    else:
      _LOGGER.warning("Empty data found when expecting JSON data")
    
    if value is None:
      value = None
    elif self._val_tpl is not None:
      value = self._val_tpl.render_with_possible_json_value(
        value, None)
      self._state = value
"""        try:
            data = self.download().strip()
        except (Exception):
            return

        if self._val_tpl is not None:
            self._state = self._val_tpl.async_render_with_possible_json_value(
                data, None)
        else:
            self._state = data
""" 
