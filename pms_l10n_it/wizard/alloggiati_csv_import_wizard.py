# Copyright 2024 Your Company
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
import logging
import csv
import io
import base64

_logger = logging.getLogger(__name__)


class AlloggiatiCsvImportWizard(models.TransientModel):
    _name = "alloggiati.csv.import.wizard"
    _description = "Import Alloggiati Web CSV Tables"

    table_type = fields.Selection([
        ('luoghi', 'Places (Luoghi)'),
        ('tipi_documento', 'Document Types (Tipi Documento)'),
        ('tipi_alloggiato', 'Guest Types (Tipi Alloggiato)'),
        ('stati', 'Countries/States (Stati)'),
        ('comuni', 'Municipalities (Comuni)'),
    ], string="Table Type", required=True)
    
    csv_file = fields.Binary(
        string="CSV File",
        required=True,
        help="Upload the CSV file downloaded from Alloggiati Web"
    )
    
    csv_filename = fields.Char(
        string="Filename"
    )
    
    encoding = fields.Selection([
        ('utf-8', 'UTF-8'),
        ('latin-1', 'Latin-1 (ISO-8859-1)'),
        ('cp1252', 'Windows-1252'),
    ], string="File Encoding", default='utf-8', required=True)
    
    delimiter = fields.Selection([
        (';', 'Semicolon (;)'),
        (',', 'Comma (,)'),
        ('\t', 'Tab'),
        ('|', 'Pipe (|)'),
    ], string="Delimiter", default=';', required=True)
    
    has_header = fields.Boolean(
        string="Has Header Row",
        default=True,
        help="Check if the first row contains column headers"
    )
    
    update_existing = fields.Boolean(
        string="Update Existing Records",
        default=True,
        help="Update existing records with same code, or only insert new ones"
    )
    
    dry_run = fields.Boolean(
        string="Dry Run",
        default=False,
        help="Preview import without actually creating/updating records"
    )
    
    preview_data = fields.Text(
        string="Preview",
        readonly=True
    )
    
    import_summary = fields.Text(
        string="Import Summary",
        readonly=True
    )

    @api.onchange('csv_file', 'encoding', 'delimiter', 'has_header')
    def _onchange_csv_preview(self):
        """Show preview of CSV data"""
        if self.csv_file:
            try:
                csv_data = base64.b64decode(self.csv_file)
                csv_text = csv_data.decode(self.encoding)
                
                # Read first few lines for preview
                lines = csv_text.split('\n')[:6]  # First 5 data lines + header
                
                csv_reader = csv.reader(lines, delimiter=self.delimiter)
                preview_lines = []
                
                for i, row in enumerate(csv_reader):
                    if i == 0 and self.has_header:
                        preview_lines.append("HEADER: " + " | ".join(row))
                    elif len(row) > 0:  # Skip empty lines
                        preview_lines.append(f"Row {i + (0 if self.has_header else 1)}: " + " | ".join(row))
                    
                    if len(preview_lines) >= 5:  # Limit preview
                        break
                
                self.preview_data = "\n".join(preview_lines)
                
            except Exception as e:
                self.preview_data = f"Error reading file: {str(e)}"
        else:
            self.preview_data = ""

    def action_import_csv(self):
        """Import CSV data into alloggiati.table"""
        self.ensure_one()
        
        if not self.csv_file:
            raise UserError(_("Please upload a CSV file"))
        
        try:
            # Decode CSV file
            csv_data = base64.b64decode(self.csv_file)
            csv_text = csv_data.decode(self.encoding)
            
            # Parse CSV
            csv_reader = csv.reader(io.StringIO(csv_text), delimiter=self.delimiter)
            
            # Skip header if exists
            if self.has_header:
                next(csv_reader, None)
            
            # Process based on table type
            if self.table_type == 'luoghi':
                result = self._import_luoghi(csv_reader)
            elif self.table_type == 'tipi_documento':
                result = self._import_tipi_documento(csv_reader)
            elif self.table_type == 'tipi_alloggiato':
                result = self._import_tipi_alloggiato(csv_reader)
            elif self.table_type == 'stati':
                result = self._import_stati(csv_reader)
            elif self.table_type == 'comuni':
                result = self._import_comuni(csv_reader)
            else:
                raise UserError(_("Unknown table type: %s") % self.table_type)
            
            self.import_summary = result['summary']
            
            if self.dry_run:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'alloggiati.csv.import.wizard',
                    'res_id': self.id,
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {'show_summary': True}
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Import Complete'),
                        'message': result['message'],
                        'type': 'success',
                    }
                }
                
        except Exception as e:
            _logger.error("CSV import error: %s", str(e))
            raise UserError(_("Import failed: %s") % str(e))

    def _import_luoghi(self, csv_reader):
        """Import luoghi (places) data"""
        created_count = 0
        updated_count = 0
        error_count = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, start=1):
            try:
                if len(row) < 2:
                    continue
                
                code = row[0].strip()
                name = row[1].strip()
                provincia = row[2].strip() if len(row) > 2 else ""
                data_fine = row[3].strip() if len(row) > 3 else ""
                
                if not code or not name:
                    continue
                
                # Check for existing record
                existing = self.env['alloggiati.table'].search([
                    ('code', '=', code),
                    ('table_type', '=', 'luoghi')
                ], limit=1)
                
                values = {
                    'name': name,
                    'code': code,
                    'table_type': 'luoghi',
                    'description': f"Provincia: {provincia}" if provincia else "",
                    'parent_code': provincia,
                    'active': not data_fine,  # Active if no end date
                }
                
                if existing and self.update_existing and not self.dry_run:
                    existing.write(values)
                    updated_count += 1
                elif not existing and not self.dry_run:
                    self.env['alloggiati.table'].create(values)
                    created_count += 1
                elif not existing:
                    created_count += 1  # For dry run counting
                    
                # Try to update corresponding res.country or res.city
                if not self.dry_run:
                    self._update_geo_records('luoghi', code, name, provincia)
                    
            except Exception as e:
                error_count += 1
                errors.append(f"Row {row_num}: {str(e)}")
                if len(errors) > 10:  # Limit error list
                    errors.append("... (more errors)")
                    break
        
        summary = f"Luoghi Import Results:\n"
        summary += f"- Created: {created_count}\n"
        summary += f"- Updated: {updated_count}\n"
        summary += f"- Errors: {error_count}\n"
        if errors:
            summary += f"\nErrors:\n" + "\n".join(errors[:10])
        
        return {
            'summary': summary,
            'message': f"Import completed: {created_count} created, {updated_count} updated"
        }

    def _import_tipi_documento(self, csv_reader):
        """Import document types"""
        created_count = 0
        updated_count = 0
        
        for row in csv_reader:
            if len(row) < 2:
                continue
                
            code = row[0].strip()
            description = row[1].strip()
            
            if not code or not description:
                continue
            
            existing = self.env['alloggiati.table'].search([
                ('code', '=', code),
                ('table_type', '=', 'tipi_documento')
            ], limit=1)
            
            values = {
                'name': description,
                'code': code,
                'table_type': 'tipi_documento',
                'description': description,
                'active': True,
            }
            
            if existing and self.update_existing and not self.dry_run:
                existing.write(values)
                updated_count += 1
            elif not existing and not self.dry_run:
                self.env['alloggiati.table'].create(values)
                created_count += 1
            elif not existing:
                created_count += 1
        
        summary = f"Document Types Import Results:\n"
        summary += f"- Created: {created_count}\n"
        summary += f"- Updated: {updated_count}\n"
        
        return {
            'summary': summary,
            'message': f"Import completed: {created_count} created, {updated_count} updated"
        }

    def _import_tipi_alloggiato(self, csv_reader):
        """Import guest types"""
        created_count = 0
        updated_count = 0
        
        for row in csv_reader:
            if len(row) < 2:
                continue
                
            code = row[0].strip()
            description = row[1].strip()
            
            if not code or not description:
                continue
            
            existing = self.env['alloggiati.table'].search([
                ('code', '=', code),
                ('table_type', '=', 'tipi_alloggiato')
            ], limit=1)
            
            values = {
                'name': description,
                'code': code,
                'table_type': 'tipi_alloggiato',
                'description': description,
                'active': True,
            }
            
            if existing and self.update_existing and not self.dry_run:
                existing.write(values)
                updated_count += 1
            elif not existing and not self.dry_run:
                self.env['alloggiati.table'].create(values)
                created_count += 1
            elif not existing:
                created_count += 1
        
        summary = f"Guest Types Import Results:\n"
        summary += f"- Created: {created_count}\n"
        summary += f"- Updated: {updated_count}\n"
        
        return {
            'summary': summary,
            'message': f"Import completed: {created_count} created, {updated_count} updated"
        }

    def _import_stati(self, csv_reader):
        """Import countries/states"""
        created_count = 0
        updated_count = 0
        
        for row in csv_reader:
            if len(row) < 2:
                continue
                
            code = row[0].strip()
            name = row[1].strip()
            provincia = row[2].strip() if len(row) > 2 else ""
            data_fine = row[3].strip() if len(row) > 3 else ""
            
            if not code or not name:
                continue
            
            existing = self.env['alloggiati.table'].search([
                ('code', '=', code),
                ('table_type', '=', 'luoghi'),  # States are stored as luoghi
                ('name', 'ilike', name)
            ], limit=1)
            
            values = {
                'name': name,
                'code': code,
                'table_type': 'luoghi',
                'description': f"Stato/Provincia: {provincia}" if provincia else "Stato",
                'parent_code': provincia,
                'active': not data_fine,
            }
            
            if existing and self.update_existing and not self.dry_run:
                existing.write(values)
                updated_count += 1
            elif not existing and not self.dry_run:
                self.env['alloggiati.table'].create(values)
                created_count += 1
            elif not existing:
                created_count += 1
                
            # Try to update corresponding res.country
            if not self.dry_run:
                self._update_geo_records('stati', code, name, provincia)
        
        summary = f"States Import Results:\n"
        summary += f"- Created: {created_count}\n"
        summary += f"- Updated: {updated_count}\n"
        
        return {
            'summary': summary,
            'message': f"Import completed: {created_count} created, {updated_count} updated"
        }

    def _import_comuni(self, csv_reader):
        """Import municipalities"""
        created_count = 0
        updated_count = 0
        
        for row in csv_reader:
            if len(row) < 3:
                continue
                
            code = row[0].strip()
            name = row[1].strip()
            provincia = row[2].strip()
            data_fine = row[3].strip() if len(row) > 3 else ""
            
            if not code or not name:
                continue
            
            existing = self.env['alloggiati.table'].search([
                ('code', '=', code),
                ('table_type', '=', 'luoghi')
            ], limit=1)
            
            values = {
                'name': name,
                'code': code,
                'table_type': 'luoghi',
                'description': f"Comune in provincia di {provincia}",
                'parent_code': provincia,
                'active': not data_fine,
            }
            
            if existing and self.update_existing and not self.dry_run:
                existing.write(values)
                updated_count += 1
            elif not existing and not self.dry_run:
                self.env['alloggiati.table'].create(values)
                created_count += 1
            elif not existing:
                created_count += 1
                
            # Try to update corresponding res.city
            if not self.dry_run:
                self._update_geo_records('comuni', code, name, provincia)
        
        summary = f"Municipalities Import Results:\n"
        summary += f"- Created: {created_count}\n"
        summary += f"- Updated: {updated_count}\n"
        
        return {
            'summary': summary,
            'message': f"Import completed: {created_count} created, {updated_count} updated"
        }

    def _update_geo_records(self, table_type, code, name, parent_code):
        """Update corresponding geographic records in Odoo"""
        try:
            if table_type in ['stati']:
                # Try to match with res.country
                country = self.env['res.country'].search([
                    '|', ('name', 'ilike', name), ('code', 'ilike', name[:2])
                ], limit=1)
                
                if country:
                    country.write({
                        'alloggiati_web_code': code,
                        'alloggiati_web_active': True
                    })
                    
            elif table_type in ['comuni', 'luoghi']:
                # Try to match with res.city (for Italian municipalities)
                if parent_code:  # Has province, likely Italian city
                    # First try to find the province/state
                    state = self.env['res.country.state'].search([
                        ('code', 'ilike', parent_code),
                        ('country_id.code', '=', 'IT')
                    ], limit=1)
                    
                    if state:
                        city = self.env['res.city'].search([
                            ('name', 'ilike', name),
                            ('state_id', '=', state.id)
                        ], limit=1)
                        
                        if city:
                            city.write({
                                'alloggiati_web_code': code,
                                'alloggiati_web_active': True
                            })
                        
        except Exception as e:
            _logger.warning("Error updating geo record for %s: %s", name, str(e))

    def action_download_sample(self):
        """Download sample CSV file for the selected table type"""
        self.ensure_one()
        
        samples = {
            'luoghi': 'Codice;Descrizione;Provincia;DataFineVal\n100000001;ITALIA;;',
            'tipi_documento': 'Codice;Descrizione\n1;CARTA DI IDENTITA\n2;PASSAPORTO',
            'tipi_alloggiato': 'Codice;Descrizione\n16;OSPITI DI ALBERGO\n17;OSPITI DI VILLAGGIO',
            'stati': 'Codice;Descrizione;Provincia;DataFineVal\n100000001;ITALIA;;',
            'comuni': 'Codice;Descrizione;Provincia;DataFineVal\n415063001;BOLZANO;BZ;',
        }
        
        if self.table_type in samples:
            sample_content = samples[self.table_type]
            sample_filename = f"sample_{self.table_type}.csv"
            
            return {
                'type': 'ir.actions.act_url',
                'url': f'data:text/csv;base64,{base64.b64encode(sample_content.encode()).decode()}',
                'target': 'new',
            }
        
        raise UserError(_("No sample available for this table type"))