"""
email_report.py — Generación y envío de informes de consumo energético por email.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta

# ── Configuración Gmail ───────────────────────────────────────────────────────
GMAIL_USER     = "peihaosun2007@gmail.com"
GMAIL_PASSWORD = "npii mysb ujgp imxj"
EMAIL_DESTINO  = "peihaosun2007@gmail.com"


def build_html_report(stats: dict) -> str:
    """Genera el HTML del informe de consumo."""

    filas = ""
    for sp in stats["spaces"]:
        filas += f"""
        <tr>
            <td style="padding:10px 14px;border-bottom:1px solid #eee;font-weight:600;">{sp['space_code']}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #eee;color:#555;">{sp['space_label']}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #eee;text-align:center;">{sp['total_hours']:.1f} h</td>
            <td style="padding:10px 14px;border-bottom:1px solid #eee;text-align:center;">{sp['total_kwh']:.3f} kWh</td>
            <td style="padding:10px 14px;border-bottom:1px solid #eee;text-align:center;color:#8A5E10;font-weight:600;">{sp['cost_eur']:.4f} €</td>
        </tr>"""

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#F2EFE8;font-family:'Segoe UI',Arial,sans-serif;">
        <div style="max-width:640px;margin:32px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

            <!-- Cabecera -->
            <div style="background:#3D5A3E;padding:28px 32px;">
                <div style="display:flex;align-items:center;gap:12px;">
                    <div style="background:rgba(255,255,255,0.15);border-radius:8px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;font-size:18px;">🏢</div>
                    <div>
                        <div style="color:#fff;font-size:18px;font-weight:700;letter-spacing:-0.3px;">DeskFlow</div>
                        <div style="color:rgba(255,255,255,0.6);font-size:12px;">Informe de consumo energético</div>
                    </div>
                </div>
            </div>

            <!-- Período -->
            <div style="padding:24px 32px 0;">
                <div style="font-size:13px;color:#999;text-transform:uppercase;letter-spacing:0.06em;font-weight:600;margin-bottom:4px;">Período analizado</div>
                <div style="font-size:22px;font-weight:700;color:#1A1814;letter-spacing:-0.4px;">{stats['period'].capitalize()}</div>
                <div style="font-size:12px;color:#999;margin-top:4px;">{stats['from_date'][:10]} → {stats['to_date'][:10]}</div>
            </div>

            <!-- Resumen -->
            <div style="padding:20px 32px;display:flex;gap:16px;">
                <div style="flex:1;background:#F2EFE8;border-radius:10px;padding:16px;text-align:center;">
                    <div style="font-size:24px;font-weight:700;color:#3D5A3E;">{stats['total_kwh']:.2f}</div>
                    <div style="font-size:11px;color:#888;margin-top:4px;">kWh totales</div>
                </div>
                <div style="flex:1;background:#FAECD6;border-radius:10px;padding:16px;text-align:center;">
                    <div style="font-size:24px;font-weight:700;color:#8A5E10;">{stats['total_cost_eur']:.2f} €</div>
                    <div style="font-size:11px;color:#888;margin-top:4px;">Coste estimado</div>
                </div>
                <div style="flex:1;background:#F7F4EE;border-radius:10px;padding:16px;text-align:center;">
                    <div style="font-size:24px;font-weight:700;color:#2A5F8A;">{stats['price_per_kwh']:.2f} €</div>
                    <div style="font-size:11px;color:#888;margin-top:4px;">Precio/kWh</div>
                </div>
            </div>

            <!-- Tabla detalle -->
            <div style="padding:0 32px 32px;">
                <div style="font-size:13px;color:#999;text-transform:uppercase;letter-spacing:0.06em;font-weight:600;margin-bottom:12px;">Detalle por espacio</div>
                <table style="width:100%;border-collapse:collapse;font-size:13px;">
                    <thead>
                        <tr style="background:#F7F4EE;">
                            <th style="padding:10px 14px;text-align:left;font-size:11px;color:#888;font-weight:600;text-transform:uppercase;">Código</th>
                            <th style="padding:10px 14px;text-align:left;font-size:11px;color:#888;font-weight:600;text-transform:uppercase;">Espacio</th>
                            <th style="padding:10px 14px;text-align:center;font-size:11px;color:#888;font-weight:600;text-transform:uppercase;">Horas</th>
                            <th style="padding:10px 14px;text-align:center;font-size:11px;color:#888;font-weight:600;text-transform:uppercase;">kWh</th>
                            <th style="padding:10px 14px;text-align:center;font-size:11px;color:#888;font-weight:600;text-transform:uppercase;">Coste</th>
                        </tr>
                    </thead>
                    <tbody>{filas}</tbody>
                </table>
            </div>

            <!-- Footer -->
            <div style="background:#F7F4EE;padding:16px 32px;text-align:center;font-size:11px;color:#aaa;">
                Generado automáticamente por DeskFlow · {datetime.now().strftime('%d/%m/%Y %H:%M')}
            </div>
        </div>
    </body>
    </html>
    """


def send_energy_report(stats: dict, period_label: str = "semanal") -> bool:
    """Envía el informe de consumo por email. Devuelve True si tuvo éxito."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"DeskFlow — Informe {period_label} de consumo energético"
        msg["From"]    = GMAIL_USER
        msg["To"]      = EMAIL_DESTINO

        html = build_html_report(stats)
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, EMAIL_DESTINO, msg.as_string())

        return True
    except Exception as e:
        print(f"Error enviando email: {e}")
        return False
