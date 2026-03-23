import os
from dotenv import load_dotenv
import uuid
import json
from datetime import datetime
import sys
sys.path.append('/app/backend')
from utils.date_utils import now_utc
from database import db

load_dotenv()



class ContractService:
    @staticmethod
    def generate_policy_snapshot(appointment_id: str, appointment_data: dict, organizer_data: dict) -> dict:
        snapshot_id = str(uuid.uuid4())
        
        snapshot = {
            "snapshot_id": snapshot_id,
            "appointment_id": appointment_id,
            "created_at": now_utc().isoformat(),
            "is_immutable": True,
            "contract_version": "1.0",
            "terms": {
                "appointment_title": appointment_data['title'],
                "appointment_type": appointment_data['appointment_type'],
                "location": appointment_data.get('location'),
                "meeting_provider": appointment_data.get('meeting_provider'),
                "start_datetime": appointment_data['start_datetime'],
                "duration_minutes": appointment_data['duration_minutes'],
                "tolerated_delay_minutes": appointment_data['tolerated_delay_minutes'],
                "cancellation_deadline_hours": appointment_data['cancellation_deadline_hours'],
                "penalty_amount": appointment_data['penalty_amount'],
                "penalty_currency": appointment_data['penalty_currency'],
                "payout_split": {
                    "affected_compensation_percent": appointment_data['affected_compensation_percent'],
                    "platform_commission_percent": appointment_data['platform_commission_percent'],
                    "charity_percent": appointment_data.get('charity_percent', 0.0),
                    "charity_association_id": appointment_data.get('charity_association_id'),
                    "charity_association_name": appointment_data.get('charity_association_name')
                },
                "organizer": {
                    "name": f"{organizer_data['first_name']} {organizer_data['last_name']}",
                    "email": organizer_data['email']
                }
            },
            "consent_language": {
                "fr": "En acceptant ce rendez-vous, je m'engage à respecter les conditions d'engagement définies ci-dessus. Je comprends qu'en cas de retard dépassant la tolérance accordée ou d'absence non justifiée, une pénalité financière pourra être appliquée conformément aux termes acceptés."
            }
        }
        
        db.policy_snapshots.insert_one(snapshot)
        return snapshot
    
    @staticmethod
    def generate_html_contract(snapshot: dict, participant_data: dict) -> str:
        terms = snapshot['terms']
        
        html = f"""
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: 'Inter', Arial, sans-serif;
                    line-height: 1.8;
                    color: #334155;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 40px 20px;
                }}
                .contract-header {{
                    border-top: 4px solid #0F172A;
                    padding-top: 30px;
                    margin-bottom: 40px;
                }}
                h1 {{
                    font-size: 28px;
                    color: #0F172A;
                    margin-bottom: 10px;
                }}
                .contract-meta {{
                    background: #F8FAFC;
                    padding: 20px;
                    border-left: 4px solid #10B981;
                    margin: 20px 0;
                }}
                .section {{
                    margin: 30px 0;
                }}
                .section-title {{
                    font-size: 18px;
                    font-weight: 600;
                    color: #0F172A;
                    margin-bottom: 10px;
                }}
                .terms-list {{
                    list-style: none;
                    padding-left: 0;
                }}
                .terms-list li {{
                    padding: 10px 0;
                    border-bottom: 1px solid #E2E8F0;
                }}
                .highlight {{
                    background: #FEF3C7;
                    padding: 2px 6px;
                    border-radius: 3px;
                }}
                .signature-section {{
                    margin-top: 50px;
                    padding-top: 30px;
                    border-top: 2px solid #E2E8F0;
                }}
            </style>
        </head>
        <body>
            <div class="contract-header">
                <h1>Contrat d'Engagement - NLYT</h1>
                <p style="color: #64748B;">Numéro de contrat : {snapshot['snapshot_id']}</p>
                <p style="color: #64748B;">Date de création : {snapshot['created_at']}</p>
            </div>
            
            <div class="contract-meta">
                <h2 style="margin-top: 0;">{terms['appointment_title']}</h2>
                <p><strong>Type :</strong> {terms['appointment_type']}</p>
                <p><strong>Date et heure :</strong> {terms['start_datetime']}</p>
                <p><strong>Durée :</strong> {terms['duration_minutes']} minutes</p>
                {f"<p><strong>Lieu :</strong> {terms['location']}</p>" if terms.get('location') else ""}
                {f"<p><strong>Plateforme :</strong> {terms['meeting_provider']}</p>" if terms.get('meeting_provider') else ""}
            </div>
            
            <div class="section">
                <div class="section-title">Organisateur</div>
                <p>{terms['organizer']['name']} ({terms['organizer']['email']})</p>
            </div>
            
            <div class="section">
                <div class="section-title">Participant</div>
                <p>{participant_data['first_name']} {participant_data['last_name']} ({participant_data['email']})</p>
            </div>
            
            <div class="section">
                <div class="section-title">Conditions d'engagement</div>
                <ul class="terms-list">
                    <li><strong>Retard toléré :</strong> {terms['tolerated_delay_minutes']} minutes maximum</li>
                    <li><strong>Délai d'annulation :</strong> {terms['cancellation_deadline_hours']} heures avant le rendez-vous</li>
                    <li><strong>Montant de la pénalité :</strong> <span class="highlight">{terms['penalty_amount']} {terms['penalty_currency'].upper()}</span></li>
                </ul>
            </div>
            
            <div class="section">
                <div class="section-title">Répartition des pénalités</div>
                <ul class="terms-list">
                    <li>Compensation participants affectés : {terms['payout_split']['affected_compensation_percent']}%</li>
                    <li>Commission plateforme : {terms['payout_split']['platform_commission_percent']}%</li>
                    {f"<li>Don caritatif : {terms['payout_split']['charity_percent']}%</li>" if terms['payout_split'].get('charity_percent', 0) > 0 else ""}
                </ul>
            </div>
            
            <div class="section">
                <div class="section-title">Consentement</div>
                <p style="font-style: italic; background: #FEF3C7; padding: 15px; border-radius: 6px;">
                    {snapshot['consent_language']['fr']}
                </p>
            </div>
            
            <div class="signature-section">
                <p><strong>Date d'acceptation :</strong> {datetime.now().strftime('%d/%m/%Y %H:%M:%S UTC')}</p>
                <p style="color: #64748B; font-size: 14px;">Ce contrat est juridiquement contraignant une fois accepté par signature électronique.</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    @staticmethod
    def record_acceptance(appointment_id: str, participant_id: str, snapshot_id: str, 
                         ip_address: str, user_agent: str, locale: str, timezone: str,
                         signer_name: str, signer_email: str) -> dict:
        acceptance_id = str(uuid.uuid4())
        
        acceptance = {
            "acceptance_id": acceptance_id,
            "appointment_id": appointment_id,
            "participant_id": participant_id,
            "policy_snapshot_id": snapshot_id,
            "accepted_at": now_utc().isoformat(),
            "acceptance_metadata": {
                "ip_address": ip_address,
                "user_agent": user_agent,
                "locale": locale,
                "timezone": timezone,
                "signer_name": signer_name,
                "signer_email": signer_email
            }
        }
        
        db.acceptances.insert_one(acceptance)
        return acceptance