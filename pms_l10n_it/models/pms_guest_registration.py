# Copyright 2024 Your Company
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
import logging
from datetime import datetime, date
import requests
import xml.etree.ElementTree as ET

_logger = logging.getLogger(__name__)


class PmsGuestRegistration(models.Model):
    _name = "pms.guest.registration"
    _description = "Italian Guest Registration"
    _order = "registration_date desc"
    _rec_name = "display_name"

    display_name = fields.Char(
        string="Name",
        compute="_compute_display_name",
        store=True
    )
    
    property_id = fields.Many2one(
        "pms.property",
        string="Property",
        required=True,
        ondelete="cascade"
    )
    
    registration_date = fields.Date(
        string="Registration Date",
        required=True,
        default=fields.Date.today
    )
    
    checkin_partner_ids = fields.Many2many(
        "pms.checkin.partner",
        string="Guests to Register"
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('error', 'Error'),
        ('cancelled', 'Cancelled'),
    ], string="Status", default='draft', required=True)
    
    transmission_date = fields.Datetime(
        string="Transmission Date",
        readonly=True,
        help="Date and time when the registration was sent"
    )
    
    response_message = fields.Text(
        string="Response Message",
        readonly=True,
        help="Response message from Alloggiati Web service"
    )
    
    error_message = fields.Text(
        string="Error Message",
        readonly=True,
        help="Error message in case of transmission failure"
    )
    
    guest_count = fields.Integer(
        string="Guest Count",
        compute="_compute_guest_count",
        store=True
    )
    
    xml_content = fields.Text(
        string="XML Content",
        readonly=True,
        help="Generated content for the registration"
    )

    @api.depends('registration_date', 'property_id')
    def _compute_display_name(self):
        for record in self:
            if record.property_id and record.registration_date:
                record.display_name = f"{record.property_id.name} - {record.registration_date}"
            else:
                record.display_name = _("New Registration")

    @api.depends('checkin_partner_ids')
    def _compute_guest_count(self):
        for record in self:
            record.guest_count = len(record.checkin_partner_ids)

    def action_send_registration(self):
        """Send guest registration to Alloggiati Web"""
        self.ensure_one()
        
        if not self.checkin_partner_ids:
            raise UserError(_("Please select at least one guest to register."))
            
        if not self.property_id.it_guest_registration_enabled:
            raise UserError(_("Italian guest registration is not enabled for this property."))
        
        try:
            # Generate Schedine records according to official format
            schedine_list = self._generate_schedine_records()
            
            if not schedine_list:
                raise UserError(_("No valid guest records could be generated."))
            
            # Store the generated records for review
            self.xml_content = '\n'.join(schedine_list)
            
            # Send to Alloggiati Web
            response = self._send_to_alloggiati_web(schedine_list)
            
            # Update state based on response
            if response.get('success'):
                self.state = 'sent'
                self.transmission_date = fields.Datetime.now()
                self.response_message = response.get('message', '')
                self.property_id.last_registration_date = fields.Datetime.now()
                self.property_id.registration_count += 1
                
                # Mark guests as registered
                self.checkin_partner_ids.write({'it_registered': True})
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Registration Sent'),
                        'message': _('Guest registration sent successfully!'),
                        'type': 'success',
                    }
                }
            else:
                self.state = 'error'
                self.error_message = response.get('error', _('Unknown error'))
                raise UserError(_('Registration failed: %s') % self.error_message)
                
        except UserError:
            # Re-raise UserError to show proper message
            raise
        except Exception as e:
            self.state = 'error'
            self.error_message = str(e)
            _logger.error("Guest registration failed: %s", str(e))
            raise UserError(_('Registration failed: %s') % str(e))

    def _test_schedine(self, schedine_list):
        """Test schedine records format without sending to Alloggiati Web"""
        try:
            # First, get authentication token
            token_info = self._get_authentication_token()
            if not token_info.get('success'):
                return token_info
            
            token = token_info['token']
            username = self.property_id.alloggiati_web_username
            
            # Prepare SOAP envelope for Test method
            soap_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:all="AlloggiatiService">
    <soap:Header/>
    <soap:Body>
        <all:Test>
            <all:Utente>{username}</all:Utente>
            <all:token>{token}</all:token>
            <all:ElencoSchedine>
"""
            
            # Add each schedina record
            for schedina in schedine_list:
                soap_envelope += f"                <all:string>{schedina}</all:string>\n"
            
            soap_envelope += """            </all:ElencoSchedine>
        </all:Test>
    </soap:Body>
</soap:Envelope>"""

            # Send SOAP request
            url = "https://alloggiatiweb.poliziadistato.it/service/service.asmx"
            headers = {
                'Content-Type': 'application/soap+xml; charset=utf-8',
                'SOAPAction': 'AlloggiatiService/Test'
            }
            
            if self.property_id.alloggiati_web_test_mode:
                # In test mode, simulate validation
                return {
                    'success': True,
                    'message': f'Test mode - {len(schedine_list)} schedine records validated successfully'
                }
            
            response = requests.post(url, data=soap_envelope, headers=headers, timeout=60)
            
            if response.status_code == 200:
                # Parse SOAP response
                return self._parse_test_response(response.text)
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {response.text}'
                }
                
        except requests.exceptions.Timeout as timeout_err:
            _logger.error("Timeout error testing schedine: %s", str(timeout_err))
            return {
                'success': False,
                'error': f'Request timeout: {str(timeout_err)}'
            }
        except requests.exceptions.RequestException as req_err:
            _logger.error("Network error testing schedine: %s", str(req_err))
            return {
                'success': False,
                'error': f'Network error: {str(req_err)}'
            }
        except Exception as e:
            _logger.error("Unexpected error testing schedine: %s", str(e))
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }

    def _parse_test_response(self, response_text):
        """Parse SOAP response from Test method"""
        try:
            root = ET.fromstring(response_text)
            
            # Look for general result
            esito_elem = root.find('.//*[contains(local-name(), "esito")]')
            if esito_elem is not None and esito_elem.text == 'true':
                # Look for schedine valide count
                valide_elem = root.find('.//*[contains(local-name(), "SchedineValide")]')
                count = valide_elem.text if valide_elem is not None else '0'
                
                return {
                    'success': True,
                    'message': f'Validation successful. {count} valid schedine records found.'
                }
            else:
                # Look for error details
                error_elem = root.find('.//*[contains(local-name(), "ErroreDes")]')
                error_msg = error_elem.text if error_elem is not None else 'Unknown validation error'
                
                return {
                    'success': False,
                    'error': f'Validation failed: {error_msg}'
                }
                
        except ET.ParseError as e:
            return {
                'success': False,
                'error': f'XML parsing error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Response parsing error: {str(e)}'
            }

    def _generate_schedine_records(self):
        """Generate Schedine records according to Alloggiati Web tracciato record"""
        schedine_list = []
        
        for guest in self.checkin_partner_ids:
            # Create fixed-length record according to documentation (168 characters)
            record = self._create_guest_record(guest)
            if record:
                schedine_list.append(record)
        
        return schedine_list
    
    def _create_guest_record(self, guest):
        """Create a single guest record following the tracciato specifications"""
        try:
            # Initialize record with spaces (168 characters total)
            record = [' '] * 168
            
            # Tipo Alloggiato (0-1) - Default to "16" for hotel guests
            tipo_alloggiato = "16"
            record[0:2] = list(tipo_alloggiato.ljust(2)[:2])
            
            # Data Arrivo (2-11) - gg/mm/aaaa format
            if guest.arrival:
                data_arrivo = guest.arrival.strftime("%d/%m/%Y")
                record[2:12] = list(data_arrivo.ljust(10)[:10])
            
            # Numero Giorni di Permanenza (12-13) - Max 30 days
            if guest.arrival and guest.departure:
                giorni = (guest.departure.date() - guest.arrival.date()).days
                giorni = min(giorni, 30)  # Max 30 days
                record[12:14] = list(f"{giorni:02d}")
            
            # Cognome (14-63) - 50 characters
            cognome = (guest.lastname or "").upper()
            record[14:64] = list(cognome.ljust(50)[:50])
            
            # Nome (64-93) - 30 characters  
            nome = (guest.firstname or "").upper()
            record[64:94] = list(nome.ljust(30)[:30])
            
            # Sesso (94) - 1=M, 2=F
            if guest.gender:
                sesso = "1" if guest.gender.upper() == "M" else "2"
                record[94] = sesso
            
            # Data Nascita (95-104) - gg/mm/aaaa
            if guest.birthdate_date:
                data_nascita = guest.birthdate_date.strftime("%d/%m/%Y")
                record[95:105] = list(data_nascita.ljust(10)[:10])
            
            # Comune Nascita (105-113) - 9 characters (if Italy)
            if guest.residence_country_id and guest.residence_country_id.code == "IT":
                comune_code = self._get_comune_code(guest.residence_city_id)
                record[105:114] = list(comune_code.ljust(9)[:9])
            
            # Provincia Nascita (114-115) - 2 characters (if Italy)
            if guest.residence_country_id and guest.residence_country_id.code == "IT":
                provincia = (guest.residence_state_id.code or "").upper()
                record[114:116] = list(provincia.ljust(2)[:2])
            
            # Stato Nascita (116-124) - 9 characters
            stato_code = self._get_stato_code(guest.residence_country_id)
            record[116:125] = list(stato_code.ljust(9)[:9])
            
            # Cittadinanza (125-133) - 9 characters
            cittadinanza_code = self._get_stato_code(guest.nationality_id)
            record[125:134] = list(cittadinanza_code.ljust(9)[:9])
            
            # Tipo Documento (134-138) - 5 characters
            tipo_doc = self._get_document_type_code(guest.document_type)
            record[134:139] = list(tipo_doc.ljust(5)[:5])
            
            # Numero Documento (139-158) - 20 characters
            numero_doc = (guest.document_number or "").upper()
            record[139:159] = list(numero_doc.ljust(20)[:20])
            
            # Luogo Rilascio Documento (159-167) - 9 characters
            luogo_rilascio = self._get_document_place_code(guest)
            record[159:168] = list(luogo_rilascio.ljust(9)[:9])
            
            return ''.join(record)
            
        except (AttributeError, ValueError, TypeError) as data_err:
            _logger.error("Data error creating guest record for %s: %s", guest.display_name, str(data_err))
            return None
        except Exception as e:
            _logger.error("Unexpected error creating guest record for %s: %s", guest.display_name, str(e))
            return None
    
    def _get_comune_code(self, city_id):
        """Get the official comune code from Alloggiati Web tables"""
        if not city_id:
            return "000000000"
        
        # First try to get from the city's alloggiati_web_code
        alloggiati_code = self.env['res.city'].get_alloggiati_code(city_id)
        if alloggiati_code and alloggiati_code != "000000000":
            return alloggiati_code
        
        # Fallback: search in alloggiati.table
        table_record = self.env['alloggiati.table'].search([
            ('table_type', '=', 'luoghi'),
            ('name', 'ilike', city_id.name)
        ], limit=1)
        
        if table_record:
            return table_record.code
            
        return "000000000"
    
    def _get_stato_code(self, country_id):
        """Get the official state code from Alloggiati Web tables"""
        if not country_id:
            return "000000000"
        
        # Use the new method from res.country
        return self.env['res.country'].get_alloggiati_code(country_id)
    
    def _get_document_type_code(self, document_type):
        """Get document type code according to Alloggiati Web tables"""
        if not document_type:
            return ""
        
        # First try from alloggiati.table
        table_record = self.env['alloggiati.table'].search([
            ('table_type', '=', 'tipi_documento'),
            ('name', 'ilike', document_type)
        ], limit=1)
        
        if table_record:
            return table_record.code
        
        # Fallback mappings
        type_mappings = {
            "passport": "1",
            "id_card": "2", 
            "driving_license": "3",
            "other": "4"
        }
        return type_mappings.get(document_type, "")
    
    def _get_document_place_code(self, guest):
        """Get document place code"""
        # For Italian documents, try to get city code
        if guest.residence_country_id and guest.residence_country_id.code == "IT":
            if guest.residence_city_id:
                return self._get_comune_code(guest.residence_city_id)
            return self.env['res.country'].get_alloggiati_code(guest.residence_country_id)
        
        # For foreign documents, use country code
        if guest.residence_country_id:
            return self.env['res.country'].get_alloggiati_code(guest.residence_country_id)
            
        return "000000000"

    def _send_to_alloggiati_web(self, schedine_list):
        """Send Schedine records to Alloggiati Web service using SOAP"""
        try:
            # First, get authentication token
            token_info = self._get_authentication_token()
            if not token_info.get('success'):
                return token_info
            
            token = token_info['token']
            username = self.property_id.alloggiati_web_username
            
            # Prepare SOAP envelope for Send method
            soap_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:all="AlloggiatiService">
    <soap:Header/>
    <soap:Body>
        <all:Send>
            <all:Utente>{username}</all:Utente>
            <all:token>{token}</all:token>
            <all:ElencoSchedine>
"""
            
            # Add each schedina record
            for schedina in schedine_list:
                soap_envelope += f"                <all:string>{schedina}</all:string>\n"
            
            soap_envelope += """            </all:ElencoSchedine>
        </all:Send>
    </soap:Body>
</soap:Envelope>"""

            # Send SOAP request
            url = "https://alloggiatiweb.poliziadistato.it/service/service.asmx"
            headers = {
                'Content-Type': 'application/soap+xml; charset=utf-8',
                'SOAPAction': 'AlloggiatiService/Send'
            }
            
            if self.property_id.alloggiati_web_test_mode:
                # In test mode, simulate success
                return {
                    'success': True,
                    'message': f'Test mode - {len(schedine_list)} guest records processed successfully'
                }
            
            response = requests.post(url, data=soap_envelope, headers=headers, timeout=60)
            
            if response.status_code == 200:
                # Parse SOAP response
                return self._parse_soap_response(response.text)
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {response.text}'
                }
                
        except requests.exceptions.Timeout as timeout_err:
            _logger.error("Timeout error sending to Alloggiati Web: %s", str(timeout_err))
            return {
                'success': False,
                'error': f'Request timeout: {str(timeout_err)}'
            }
        except requests.exceptions.RequestException as req_err:
            _logger.error("Network error sending to Alloggiati Web: %s", str(req_err))
            return {
                'success': False,
                'error': f'Network error: {str(req_err)}'
            }
        except Exception as e:
            _logger.error("Unexpected error sending to Alloggiati Web: %s", str(e))
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }

    def _get_authentication_token(self):
        """Get authentication token from Alloggiati Web"""
        try:
            username = self.property_id.alloggiati_web_username
            password = self.property_id.alloggiati_web_password
            wskey = self.property_id.alloggiati_web_wskey
            
            if not all([username, password, wskey]):
                return {
                    'success': False,
                    'error': 'Missing authentication credentials'
                }
            
            # Prepare SOAP envelope for GenerateToken
            soap_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:all="AlloggiatiService">
    <soap:Header/>
    <soap:Body>
        <all:GenerateToken>
            <all:Utente>{username}</all:Utente>
            <all:Password>{password}</all:Password>
            <all:WsKey>{wskey}</all:WsKey>
        </all:GenerateToken>
    </soap:Body>
</soap:Envelope>"""
            
            url = "https://alloggiatiweb.poliziadistato.it/service/service.asmx"
            headers = {
                'Content-Type': 'application/soap+xml; charset=utf-8',
                'SOAPAction': 'AlloggiatiService/GenerateToken'
            }
            
            if self.property_id.alloggiati_web_test_mode:
                # In test mode, return dummy token
                return {
                    'success': True,
                    'token': 'TEST_TOKEN_123456'
                }
            
            response = requests.post(url, data=soap_envelope, headers=headers, timeout=30)
            
            if response.status_code == 200:
                # Parse token from response
                return self._parse_token_response(response.text)
            else:
                return {
                    'success': False,
                    'error': f'Token request failed: HTTP {response.status_code}'
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Token request timeout'
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Token request network error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Token request error: {str(e)}'
            }
    
    def _parse_token_response(self, response_text):
        """Parse token from SOAP response"""
        try:
            root = ET.fromstring(response_text)
            
            # Look for token in response
            for elem in root.iter():
                if 'token' in elem.tag.lower():
                    return {
                        'success': True,
                        'token': elem.text
                    }
            
            # If no token found, check for errors
            for elem in root.iter():
                if 'esito' in elem.tag.lower() and elem.text == 'false':
                    error_elem = root.find('.//*[contains(local-name(), "ErroreDes")]')
                    error_msg = error_elem.text if error_elem is not None else 'Unknown error'
                    return {
                        'success': False,
                        'error': f'Authentication failed: {error_msg}'
                    }
            
            return {
                'success': False,
                'error': 'Invalid response format'
            }
            
        except ET.ParseError as e:
            return {
                'success': False,
                'error': f'XML parsing error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Response parsing error: {str(e)}'
            }
    
    def _parse_soap_response(self, response_text):
        """Parse SOAP response from Send method"""
        try:
            root = ET.fromstring(response_text)
            
            # Look for general result
            esito_elem = root.find('.//*[contains(local-name(), "esito")]')
            if esito_elem is not None and esito_elem.text == 'true':
                # Look for schedine valide count
                valide_elem = root.find('.//*[contains(local-name(), "SchedineValide")]')
                count = valide_elem.text if valide_elem is not None else '0'
                
                return {
                    'success': True,
                    'message': f'Registration successful. {count} valid guest records processed.'
                }
            else:
                # Look for error details
                error_elem = root.find('.//*[contains(local-name(), "ErroreDes")]')
                error_msg = error_elem.text if error_elem is not None else 'Unknown error'
                
                return {
                    'success': False,
                    'error': f'Registration failed: {error_msg}'
                }
                
        except ET.ParseError as e:
            return {
                'success': False,
                'error': f'XML parsing error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Response parsing error: {str(e)}'
            }

    def action_cancel(self):
        """Cancel the registration"""
        self.state = 'cancelled'

    def action_reset_to_draft(self):
        """Reset to draft state"""
        self.state = 'draft'
        self.transmission_date = False
        self.response_message = False
        self.error_message = False