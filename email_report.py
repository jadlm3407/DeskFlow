"""
email_report.py — Generación y envío de informes de consumo energético por email.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ── Configuración Gmail ───────────────────────────────────────────────────────
GMAIL_USER     = "deskflow.espacios@gmail.com"
GMAIL_PASSWORD = "roqm yius qrnx jkyv"
EMAIL_DESTINO_DEFAULT = "peihaosun2007@gmail.com"

# ── Constantes descriptivas ───────────────────────────────────────────────────
SALA_DEVICE_DESC        = "AC 1 500 W + 8 tubos LED 40 W = 1 820 W"
WORKSTATION_DEVICE_DESC = "PC 200 W + Monitor 30 W + Lámpara 10 W = 240 W"

# ── Paleta por sala ───────────────────────────────────────────────────────────
_SALA_COLORS = {
    "SP1": {"accent": "#3D5A3E", "light": "#EBF5EC", "border": "#B8D9BC"},
    "SP2": {"accent": "#1E5FA8", "light": "#E8F0FB", "border": "#A8C4E8"},
}
_DEFAULT_COLOR = {"accent": "#555", "light": "#F2EFE8", "border": "#ddd"}

def _c(code: str) -> dict:
    return _SALA_COLORS.get(code, _DEFAULT_COLOR)


def _sala_section(sala: dict) -> str:
    c = _c(sala["zone_code"])
    rows = ""
    active_spaces = [sp for sp in sala["spaces"] if sp["total_hours"] > 0]
    if active_spaces:
        for sp in active_spaces:
            rows += f"""
            <tr>
              <td style="padding:8px 14px;border-bottom:1px solid #eee;font-family:monospace;font-weight:600;">{sp['space_code']}</td>
              <td style="padding:8px 14px;border-bottom:1px solid #eee;color:#555;">{sp['space_label']}</td>
              <td style="padding:8px 14px;border-bottom:1px solid #eee;text-align:center;">{sp['total_hours']:.1f} h</td>
              <td style="padding:8px 14px;border-bottom:1px solid #eee;text-align:center;">{sp['total_kwh']:.3f} kWh</td>
              <td style="padding:8px 14px;border-bottom:1px solid #eee;text-align:center;color:#8A5E10;font-weight:600;">{sp['cost_eur']:.4f} €</td>
            </tr>"""
    else:
        rows = '<tr><td colspan="5" style="padding:14px;text-align:center;color:#bbb;font-size:12px;">Sin actividad registrada en este período</td></tr>'

    return f"""
    <div style="margin:0 32px 32px;">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">
        <div style="width:4px;height:34px;background:{c['accent']};border-radius:2px;flex-shrink:0;"></div>
        <div>
          <div style="font-size:15px;font-weight:700;color:#1A1814;">{sala['zone_name']}</div>
          <div style="font-size:11px;color:#999;margin-top:2px;">
            Tiempo abierta: <strong>{sala['open_hours']:.1f} h</strong>
            &nbsp;·&nbsp; Dispositivos sala: {SALA_DEVICE_DESC}
          </div>
        </div>
      </div>
      <div style="display:flex;gap:10px;margin-bottom:16px;">
        <div style="flex:1;background:{c['light']};border:1px solid {c['border']};border-radius:10px;padding:14px;text-align:center;">
          <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;">⏱ Horas abiertas</div>
          <div style="font-size:22px;font-weight:700;color:{c['accent']};">{sala['open_hours']:.1f} h</div>
        </div>
        <div style="flex:1;background:#F2EFE8;border-radius:10px;padding:14px;text-align:center;">
          <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;">🏢 Dispositivos sala</div>
          <div style="font-size:22px;font-weight:700;color:#555;">{sala['sala_kwh']:.3f} kWh</div>
          <div style="font-size:11px;color:#8A5E10;margin-top:3px;">{sala['sala_cost_eur']:.4f} €</div>
        </div>
        <div style="flex:1;background:#F2EFE8;border-radius:10px;padding:14px;text-align:center;">
          <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;">💻 Puestos de trabajo</div>
          <div style="font-size:22px;font-weight:700;color:#555;">{sala['workstation_kwh']:.3f} kWh</div>
          <div style="font-size:11px;color:#8A5E10;margin-top:3px;">{sala['workstation_cost_eur']:.4f} €</div>
        </div>
        <div style="flex:1;background:#FAECD6;border-radius:10px;padding:14px;text-align:center;">
          <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;">🔌 Total sala</div>
          <div style="font-size:22px;font-weight:700;color:#8A5E10;">{sala['total_kwh']:.3f} kWh</div>
          <div style="font-size:12px;color:#8A5E10;margin-top:3px;font-weight:600;">{sala['total_cost_eur']:.4f} €</div>
        </div>
      </div>
      <table style="width:100%;border-collapse:collapse;font-size:12px;">
        <thead>
          <tr style="background:#F7F4EE;">
            <th style="padding:8px 14px;text-align:left;font-size:10px;color:#888;font-weight:600;text-transform:uppercase;">Código</th>
            <th style="padding:8px 14px;text-align:left;font-size:10px;color:#888;font-weight:600;text-transform:uppercase;">Puesto</th>
            <th style="padding:8px 14px;text-align:center;font-size:10px;color:#888;font-weight:600;text-transform:uppercase;">Horas</th>
            <th style="padding:8px 14px;text-align:center;font-size:10px;color:#888;font-weight:600;text-transform:uppercase;">kWh</th>
            <th style="padding:8px 14px;text-align:center;font-size:10px;color:#888;font-weight:600;text-transform:uppercase;">Coste</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""


def build_html_report(stats: dict) -> str:
    resumen_filas = ""
    for s in stats["salas"]:
        resumen_filas += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;font-weight:600;">{s['zone_name']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center;">{s['open_hours']:.1f} h</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center;">{s['total_kwh']:.3f} kWh</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center;color:#8A5E10;font-weight:600;">{s['total_cost_eur']:.4f} €</td>
        </tr>"""

    sala_sections = "".join(_sala_section(s) for s in stats["salas"])

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#F2EFE8;font-family:'Segoe UI',Arial,sans-serif;">
      <div style="max-width:700px;margin:32px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08);">
        <div style="background:#3D5A3E;padding:28px 32px;">
          <div style="display:flex;align-items:center;gap:12px;">
            <div style="background:rgba(255,255,255,.15);border-radius:8px;width:40px;height:40px;display:flex;align-items:center;justify-content:center;font-size:20px;">🏫</div>
            <div>
              <div style="color:#fff;font-size:19px;font-weight:700;">DeskFlow</div>
              <div style="color:rgba(255,255,255,.6);font-size:12px;">Informe de consumo energético — Salas de Profesores</div>
            </div>
          </div>
        </div>
        <div style="padding:24px 32px 16px;">
          <div style="font-size:11px;color:#999;text-transform:uppercase;letter-spacing:.07em;font-weight:600;margin-bottom:4px;">Período analizado</div>
          <div style="font-size:23px;font-weight:700;color:#1A1814;">{stats['period'].capitalize()}</div>
          <div style="font-size:12px;color:#999;margin-top:4px;">{stats['from_date'][:10]} → {stats['to_date'][:10]}</div>
        </div>
        <div style="padding:0 32px 16px;">
          <div style="font-size:11px;color:#999;text-transform:uppercase;letter-spacing:.07em;font-weight:600;margin-bottom:10px;">Resumen global</div>
          <div style="display:flex;gap:14px;margin-bottom:18px;">
            <div style="flex:1;background:#F2EFE8;border-radius:10px;padding:16px;text-align:center;">
              <div style="font-size:26px;font-weight:700;color:#3D5A3E;">{stats['total_kwh']:.2f}</div>
              <div style="font-size:11px;color:#888;margin-top:4px;">kWh totales</div>
            </div>
            <div style="flex:1;background:#FAECD6;border-radius:10px;padding:16px;text-align:center;">
              <div style="font-size:26px;font-weight:700;color:#8A5E10;">{stats['total_cost_eur']:.2f} €</div>
              <div style="font-size:11px;color:#888;margin-top:4px;">Coste estimado</div>
            </div>
            <div style="flex:1;background:#F7F4EE;border-radius:10px;padding:16px;text-align:center;">
              <div style="font-size:26px;font-weight:700;color:#2A5F8A;">{stats['price_per_kwh']:.2f} €</div>
              <div style="font-size:11px;color:#888;margin-top:4px;">€ / kWh</div>
            </div>
          </div>
          <table style="width:100%;border-collapse:collapse;font-size:12px;">
            <thead>
              <tr style="background:#F7F4EE;">
                <th style="padding:8px 12px;text-align:left;font-size:10px;color:#888;font-weight:600;text-transform:uppercase;">Sala</th>
                <th style="padding:8px 12px;text-align:center;font-size:10px;color:#888;font-weight:600;text-transform:uppercase;">Horas</th>
                <th style="padding:8px 12px;text-align:center;font-size:10px;color:#888;font-weight:600;text-transform:uppercase;">kWh</th>
                <th style="padding:8px 12px;text-align:center;font-size:10px;color:#888;font-weight:600;text-transform:uppercase;">Coste</th>
              </tr>
            </thead>
            <tbody>{resumen_filas}</tbody>
          </table>
        </div>
        <div style="border-top:2px solid #F2EFE8;"></div>
        <div style="padding:24px 0 0;">{sala_sections}</div>
        <div style="margin:0 32px 24px;padding:14px 16px;background:#F7F4EE;border-radius:8px;font-size:11px;color:#777;line-height:1.7;">
          <strong style="color:#444;display:block;margin-bottom:4px;">Metodología de cálculo</strong>
          🏢 <strong>Dispositivos de sala</strong> ({SALA_DEVICE_DESC}) × horas que la sala estuvo abierta.<br>
          💻 <strong>Puestos de trabajo</strong> ({WORKSTATION_DEVICE_DESC}) × horas de sesión activa por puesto.<br>
          💡 Precio aplicado: <strong>{stats['price_per_kwh']:.2f} €/kWh</strong>
        </div>
        <div style="background:#F7F4EE;padding:14px 32px;text-align:center;font-size:11px;color:#aaa;">
          Generado automáticamente por DeskFlow · {datetime.now().strftime('%d/%m/%Y %H:%M')}
        </div>
      </div>
    </body>
    </html>
    """


def send_energy_report(stats: dict, period_label: str = "semanal", email_destino: str = None) -> bool:
    """Envía el informe de consumo por email. Devuelve True si tuvo éxito."""
    destino = email_destino or EMAIL_DESTINO_DEFAULT
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"DeskFlow — Informe {period_label} de consumo energético · Salas de Profesores"
        msg["From"] = GMAIL_USER
        msg["To"]   = destino

        msg.attach(MIMEText(build_html_report(stats), "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, destino, msg.as_string())

        return True
    except Exception as e:
        print(f"Error enviando email: {e}")
        return False