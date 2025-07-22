# Copyright 2025 IT-Stecher
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _
from odoo.exceptions import UserError
import csv
import base64
import io
import logging

_logger = logging.getLogger(__name__)


class DocumentTypeImportWizard(models.TransientModel):
    _name = 'pms.document.type.import.wizard'
    _description = 'Document Type Import Wizard'

    csv_file = fields.Binary(
        string="CSV File",
        required=True,
        help="CSV file with columns: code, name"
    )
    
    csv_filename = fields.Char(string="Filename")
    
    update_existing = fields.Boolean(
        string="Update Existing",
        default=True,
        help="Update existing document types with same code"
    )
    
    deactivate_missing = fields.Boolean(
        string="Deactivate Missing",
        default=False,
        help="Deactivate document types not in import file"
    )
    
    import_result = fields.Text(
        string="Import Result",
        readonly=True
    )
    
    sample_csv = fields.Text(
        string="Sample CSV Format",
        default="""code,name
1,Passaporto
2,Carta d'identità
3,Patente di guida
4,Altro documento""",
        readonly=True,
        help="Example CSV format for import"
    )

    def action_import(self):
        """Import document types from CSV"""
        if not self.csv_file:
            raise UserError(_("Please select a CSV file to import"))
        
        try:
            # Decode CSV content
            csv_data = base64.b64decode(self.csv_file)
            csv_string = csv_data.decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(csv_string))
            
            # Validate CSV headers
            required_headers = ['code', 'name']
            if not csv_reader.fieldnames or not all(header in csv_reader.fieldnames for header in required_headers):
                raise UserError(_("CSV must contain columns: %s") % ', '.join(required_headers))
            
            created_count = 0
            updated_count = 0
            error_count = 0
            imported_codes = []
            errors = []
            
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 for header
                code = row.get('code', '').strip()
                name = row.get('name', '').strip()
                
                if not code or not name:
                    error_count += 1
                    errors.append(f"Row {row_num}: Missing code or name")
                    continue
                
                try:
                    imported_codes.append(code)
                    
                    # Suche existierende Category
                    existing_records = self.env['res.partner.id_category'].search([
                        ('alloggiati_code', '=', code)
                    ])
                    
                    if existing_records:
                        if self.update_existing:
                            existing_records.write({
                                'name': name,
                                'active': True
                            })
                            updated_count += 1
                    else:
                        # Erstelle neue Category
                        self.env['res.partner.id_category'].create({
                            'alloggiati_code': code,
                            'name': name,
                            'active': True,
                            'priority': len(imported_codes) * 10
                        })
                        created_count += 1
                        
                except Exception as e:
                    error_count += 1
                    errors.append(f"Row {row_num}: {str(e)}")
                    _logger.error(f"Error processing row {row_num}: {e}")
            
            # Deaktiviere fehlende Datensätze falls gewünscht
            deactivated_count = 0
            if self.deactivate_missing and imported_codes:
                try:
                    missing_records = self.env['res.partner.id_category'].search([
                        ('alloggiati_code', 'not in', imported_codes),
                        ('alloggiati_code', '!=', False),
                        ('active', '=', True)
                    ])
                    missing_records.write({'active': False})
                    deactivated_count = len(missing_records)
                except Exception as e:
                    errors.append(f"Error deactivating missing records: {str(e)}")
            
            # Ergebnis zusammenstellen
            result_lines = [
                f"Import completed!",
                f"✓ Created: {created_count} document types",
                f"✓ Updated: {updated_count} document types",
            ]
            
            if deactivated_count > 0:
                result_lines.append(f"✓ Deactivated: {deactivated_count} document types")
                
            if error_count > 0:
                result_lines.append(f"⚠ Errors: {error_count}")
                result_lines.append("")
                result_lines.append("Error Details:")
                result_lines.extend(errors[:10])  # Limit to first 10 errors
                if len(errors) > 10:
                    result_lines.append(f"... and {len(errors) - 10} more errors")
            
            self.import_result = '\n'.join(result_lines)
            
            _logger.info("Document types imported - Created: %d, Updated: %d, Errors: %d", 
                        created_count, updated_count, error_count)
            
            # Return view with results
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'document.type.import.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'context': {'show_result': True}
            }
            
        except Exception as e:
            _logger.error("Error importing document types: %s", str(e))
            raise UserError(_("Error importing CSV file: %s") % str(e))

    def action_close(self):
        """Close the wizard"""
        return {'type': 'ir.actions.act_window_close'}

    def action_download_sample(self):
        """Download sample CSV file"""
        sample_content = self.sample_csv
        sample_bytes = sample_content.encode('utf-8')
        sample_b64 = base64.b64encode(sample_bytes)
        
        attachment = self.env['ir.attachment'].create({
            'name': 'document_types_sample.csv',
            'datas': sample_b64,
            'mimetype': 'text/csv',
            'type': 'binary'
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def action_sync_alloggiati(self):
        """Sync document types from Alloggiati tables"""
        try:
            synced_count = self.env['res.partner.id_category'].sync_from_alloggiati_tables()
            
            if synced_count > 0:
                self.import_result = f"✓ Successfully synced {synced_count} document types from Alloggiati tables"
            else:
                self.import_result = "ℹ No document types found in Alloggiati tables to sync"
            
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'document.type.import.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'context': {'show_result': True}
            }
            
        except Exception as e:
            _logger.error("Error syncing from Alloggiati: %s", str(e))
            raise UserError(_("Error syncing from Alloggiati tables: %s") % str(e))

    @api.model
    def create_default_types(self):
        """Create default Italian document types"""
        try:
            created_count = self.env['res.partner.id_category'].create_italian_defaults()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f"Created {created_count} default document types",
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error("Error creating default types: %s", str(e))
            raise UserError(_("Error creating default document types: %s") % str(e))