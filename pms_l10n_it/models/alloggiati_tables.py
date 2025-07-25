# Copyright 2025 IT-Stecher
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _
from odoo.exceptions import UserError
import logging
import requests
import csv
import io

_logger = logging.getLogger(__name__)


class AlloggiatiTable(models.Model):
    _name = "alloggiati.table"
    _description = "Alloggiati Web Reference Tables"
    _order = "table_type, name"

    name = fields.Char(
        string="Name",
        required=True
    )
    
    table_type = fields.Selection([
        ('luoghi', 'Places (Luoghi)'),
        ('tipi_documento', 'Document Types (Tipi Documento)'),
        ('tipi_alloggiato', 'Guest Types (Tipi Alloggiato)'),
        ('lista_appartamenti', 'Apartments List'),
    ], string="Table Type", required=True)
    
    code = fields.Char(
        string="Code",
        required=True,
        help="Official code from Alloggiati Web"
    )
    
    description = fields.Text(
        string="Description"
    )
    
    parent_code = fields.Char(
        string="Parent Code",
        help="Parent code for hierarchical data (e.g., province for cities)"
    )
    
    active = fields.Boolean(
        string="Active",
        default=True
    )
    
    property_id = fields.Many2one(
        "pms.property",
        string="Property",
        help="Property for apartment tables, empty for reference tables"
    )

    _sql_constraints = [
        ('unique_code_type', 'unique(code, table_type, property_id)', 
         'Code must be unique per table type and property!')
    ]


class AlloggiatiTableManager(models.Model):
    _name = "alloggiati.table.manager"
    _description = "Alloggiati Web Table Manager"

    property_id = fields.Many2one(
        "pms.property",
        string="Property",
        required=True
    )
    
    last_sync_date = fields.Datetime(
        string="Last Sync Date",
        readonly=True
    )
    
    sync_status = fields.Selection([
        ('never', 'Never Synced'),
        ('success', 'Success'),
        ('error', 'Error'),
    ], string="Sync Status", default='never', readonly=True)
    
    table_ids = fields.One2many(
        "alloggiati.table",
        "property_id",
        string="Tables",
        readonly=True
    )

    def action_sync_all_tables(self):
        """Sync all reference tables from Alloggiati Web"""
        self.ensure_one()
        
        if not self.property_id.it_guest_registration_enabled:
            raise UserError(_("Italian guest registration is not enabled for this property."))
        
        try:
            # Get authentication token
            token_info = self._get_authentication_token()
            if not token_info.get('success'):
                raise UserError(_("Authentication failed: %s") % token_info.get('error'))
            
            token = token_info['token']
            username = self.property_id.alloggiati_web_user
            
            # Sync each table type
            table_types = ['Luoghi', 'Tipi_Documento', 'Tipi_Alloggiato', 'ListaAppartamenti']
            results = []
            
            for table_type in table_types:
                try:
                    result = self._sync_table(username, token, table_type)
                    results.append(f"{table_type}: {result}")
                except Exception as e:
                    results.append(f"{table_type}: Error - {str(e)}")
                    _logger.error("Error syncing table %s: %s", table_type, str(e))
            
            self.sync_status = 'success'
            self.sync_message = '\n'.join(results)
            self.last_sync_date = fields.Datetime.now()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Tables Synchronized'),
                    'message': _('All tables have been synchronized successfully!'),
                    'type': 'success',
                }
            }
            
        except UserError:
            # Re-raise UserError to show proper message to user
            raise
        except Exception as e:
            self.sync_status = 'error'
            self.sync_message = str(e)
            _logger.error("Error syncing Alloggiati tables: %s", str(e))
            raise UserError(_("Sync failed: %s") % str(e))

    def _get_authentication_token(self):
        """Get authentication token from Alloggiati Web"""
        # Reuse the method from guest registration
        temp_registration = self.env['pms.guest.registration'].new({
            'property_id': self.property_id.id,
        })
        return temp_registration._get_authentication_token()

    def _sync_table(self, username, token, table_type):
        """Sync a specific table from Alloggiati Web"""
        try:
            # Prepare SOAP envelope for Tabella method
            soap_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:all="AlloggiatiService">
    <soap:Header/>
    <soap:Body>
        <all:Tabella>
            <all:Utente>{username}</all:Utente>
            <all:token>{token}</all:token>
            <all:tipo>{table_type}</all:tipo>
        </all:Tabella>
    </soap:Body>
</soap:Envelope>"""
            
            url = "https://alloggiatiweb.poliziadistato.it/service/service.asmx"
            headers = {
                'Content-Type': 'application/soap+xml; charset=utf-8',
                'SOAPAction': 'AlloggiatiService/Tabella'
            }
            
            if self.property_id.alloggiati_web_test_mode:
                return f"Test mode - {table_type} sync simulated"
            
            response = requests.post(url, data=soap_envelope, headers=headers, timeout=60)
            
            if response.status_code == 200:
                csv_content = self._extract_csv_from_response(response.text)
                if csv_content:
                    return self._process_csv_data(csv_content, table_type)
                else:
                    return f"No data received for {table_type}"
            else:
                return f"HTTP {response.status_code} error"
                
        except requests.exceptions.RequestException as req_err:
            _logger.error("Network error syncing table %s: %s", table_type, str(req_err))
            raise UserError(_("Network error syncing %s: %s") % (table_type, str(req_err)))
        except Exception as e:
            _logger.error("Error syncing table %s: %s", table_type, str(e))
            raise UserError(_("Error syncing %s: %s") % (table_type, str(e)))

    def _extract_csv_from_response(self, response_text):
        """Extract CSV content from SOAP response"""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response_text)
            
            # Find CSV element
            for elem in root.iter():
                if 'CSV' in elem.tag:
                    return elem.text
            
            return None
            
        except Exception as e:
            import xml.etree.ElementTree as ET
            if isinstance(e, ET.ParseError):
                _logger.error("XML parsing error in response: %s", str(e))
                return None
            else:
                _logger.error("Error extracting CSV from response: %s", str(e))
                return None

    def _process_csv_data(self, csv_content, table_type):
        """Process CSV data and update database"""
        try:
            # Parse CSV
            csv_reader = csv.reader(io.StringIO(csv_content), delimiter=';')
            
            # Skip header row
            next(csv_reader, None)
            
            count = 0
            table_type_key = table_type.lower()
            
            # Clear existing data for this table type and property
            existing_records = self.env['alloggiati.table'].search([
                ('table_type', '=', table_type_key),
                ('property_id', '=', self.property_id.id if table_type == 'ListaAppartamenti' else False)
            ])
            existing_records.unlink()
            
            for row in csv_reader:
                if len(row) >= 2:  # At least code and name
                    self.env['alloggiati.table'].create({
                        'name': row[1].strip() if len(row) > 1 else '',
                        'code': row[0].strip(),
                        'table_type': table_type_key,
                        'description': row[2].strip() if len(row) > 2 else '',
                        'parent_code': row[3].strip() if len(row) > 3 else '',
                        'property_id': self.property_id.id if table_type == 'ListaAppartamenti' else False,
                    })
                    count += 1
            
            # Update corresponding Odoo objects
            if table_type_key == 'luoghi':
                self._update_geo_objects(table_type_key)
            elif table_type_key == 'tipi_documento':
                self._update_document_types()
            
            return f"{count} records imported"
            
        except csv.Error as csv_err:
            _logger.error("CSV parsing error for %s: %s", table_type, str(csv_err))
            raise UserError(_("CSV parsing error for %s: %s") % (table_type, str(csv_err)))
        except Exception as e:
            _logger.error("Error processing CSV data for %s: %s", table_type, str(e))
            raise UserError(_("Error processing data for %s: %s") % (table_type, str(e)))

    def _update_geo_objects(self, table_type):
        """Update countries, states, and cities with Alloggiati codes"""
        alloggiati_records = self.env['alloggiati.table'].search([
            ('table_type', '=', table_type)
        ])
        
        for record in alloggiati_records:
            # Try to match with existing Odoo objects
            # This is a simplified approach - you might need more sophisticated matching
            
            # For countries (usually shorter codes or specific patterns)
            if len(record.code) <= 3 or 'STATI' in record.name.upper():
                country = self.env['res.country'].search([
                    ('name', 'ilike', record.name)
                ], limit=1)
                if country:
                    country.write({
                        'alloggiati_web_code': record.code,
                        'alloggiati_web_active': True
                    })
            
            # For Italian cities/comuni
            elif record.parent_code:  # Has province info
                city = self.env['res.city'].search([
                    ('name', 'ilike', record.name),
                    ('country_id.code', '=', 'IT')
                ], limit=1)
                if city:
                    city.write({
                        'alloggiati_web_code': record.code,
                        'alloggiati_web_active': True
                    })

    def _update_document_types(self):
        """Update document type mappings"""
        # This could be used to populate selection fields or create lookup tables
        pass

    # Sync reference tables monthly for all properties
    def cron_sync_reference_tables(self):
        properties = self.env['pms.property'].search([('it_guest_registration_enabled', '=', True)])
        model = self.env['alloggiati.table.manager']

        for property_rec in properties:
            try:
                # Find or create table manager
                table_manager = model.search([('property_id', '=', property_rec.id)], limit=1)
                if not table_manager:
                    table_manager = model.create({'property_id': property_rec.id})
                
                # Only sync if last sync was more than 30 days ago or never synced
                from datetime import timedelta
                if (not table_manager.last_sync_date or 
                    table_manager.last_sync_date < (fields.Datetime.now() - timedelta(days=30))):
                    table_manager.action_sync_all_tables()
                    
            except Exception as e:
                import logging
                _logger = logging.getLogger(__name__)
                _logger.error("Error syncing tables for property %s: %s", property_rec.name, str(e))
