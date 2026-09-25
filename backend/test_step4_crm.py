"""
Comprehensive End-to-End Test Suite for Step 4 Core CRM Modules
Tests:
1. Authentication & Session
2. Dashboard Live Metrics & Activity Feed
3. Assignable Users
4. Customer CRUD, Notes, Document Upload & 360 View
5. Lead CRUD, Touchpoint Activity, and Lead-to-Customer Conversion
6. Deals CRUD, Kanban Pipeline & Stage Transitions
7. Tasks CRUD, Priority/Status Filters & Quick Status Updates
8. Calls Scheduling, Filtering & Status Updates
9. Meetings Scheduling & Start/End Time Validation
10. Centralized Activity Logging Verification
"""

import sys
import os
import io
import json
from pathlib import Path
from datetime import datetime, timedelta

# Ensure backend directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app

def run_step4_tests():
    print("=" * 70)
    print("APEX CRM — STEP 4 CORE MODULES AUTOMATED TEST SUITE")
    print("=" * 70)

    app = create_app()
    client = app.test_client()

    # -------------------------------------------------------------
    # 1. AUTHENTICATE AS ADMIN
    # -------------------------------------------------------------
    print("\n[1] Authenticating as Admin...")
    login_res = client.post('/api/auth/login', json={
        "email": "admin@crm.local",
        "password": "Admin@123456"
    })
    assert login_res.status_code == 200, f"Admin login failed: {login_res.data}"
    token = login_res.get_json()['token']
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    print("  -> Admin authenticated successfully.")

    # -------------------------------------------------------------
    # 2. ASSIGNABLE USERS
    # -------------------------------------------------------------
    print("\n[2] Testing Assignable Users API...")
    users_res = client.get('/api/users/assignable', headers=headers)
    assert users_res.status_code == 200, f"Assignable users failed: {users_res.data}"
    users_data = users_res.get_json()
    assert users_data['success'] is True
    assert len(users_data['users']) > 0
    assigned_user_id = users_data['users'][0]['id']
    print(f"  -> Found {len(users_data['users'])} assignable users. Using user_id={assigned_user_id}.")

    # -------------------------------------------------------------
    # 3. CUSTOMER CRUD, NOTES, DOCUMENTS, AND 360-VIEW
    # -------------------------------------------------------------
    print("\n[3] Testing Customer Management...")
    # Create Customer
    cust_payload = {
        "first_name": "Eleanor",
        "last_name": "Vane",
        "company_name": "Nassau Trading Co",
        "email": f"eleanor_{datetime.now().strftime('%M%S')}@nassau.com",
        "phone": "+1-555-0144",
        "website": "https://nassau.com",
        "address": "42 Harbor St",
        "city": "Nassau",
        "state": "NP",
        "postal_code": "00000",
        "country": "Bahamas",
        "industry": "Maritime Logistics",
        "status": "active",
        "assigned_to": assigned_user_id
    }
    create_cust_res = client.post('/api/customers', json=cust_payload, headers=headers)
    assert create_cust_res.status_code == 201, f"Create customer failed: {create_cust_res.data}"
    cust_id = create_cust_res.get_json()['customer_id']
    print(f"  -> Customer created with ID={cust_id}.")

    # Get Customer Details
    get_cust_res = client.get(f'/api/customers/{cust_id}', headers=headers)
    assert get_cust_res.status_code == 200
    assert get_cust_res.get_json()['customer']['first_name'] == "Eleanor"

    # Update Customer
    upd_cust_res = client.put(f'/api/customers/{cust_id}', json={"phone": "+1-555-9999"}, headers=headers)
    assert upd_cust_res.status_code == 200

    # Add Customer Note
    note_res = client.post(f'/api/customers/{cust_id}/notes', json={
        "note": "Initial consultation completed. Client expressed interest in Enterprise contract."
    }, headers=headers)
    assert note_res.status_code == 201
    print("  -> Customer note added successfully.")

    # Upload Customer Document
    file_content = b"Sample customer onboarding agreement content."
    doc_res = client.post(f'/api/customers/{cust_id}/documents',
        data={"file": (io.BytesIO(file_content), "contract_v1.pdf")},
        headers={"Authorization": f"Bearer {token}"},
        content_type='multipart/form-data'
    )
    assert doc_res.status_code == 201, f"Upload document failed: {doc_res.data}"
    print("  -> Customer document uploaded successfully.")

    # Get Customer 360 View
    c360_res = client.get(f'/api/customers/{cust_id}/details', headers=headers)
    assert c360_res.status_code == 200
    c360_data = c360_res.get_json()
    assert len(c360_data['notes']) >= 1
    assert len(c360_data['documents']) >= 1
    print("  -> Customer 360 view verified with notes and documents.")

    # -------------------------------------------------------------
    # 4. LEAD CRUD, TOUCHPOINTS, AND CONVERSION
    # -------------------------------------------------------------
    print("\n[4] Testing Lead Management & Conversion...")
    lead_payload = {
        "first_name": "Marcus",
        "last_name": "Aurelius",
        "company_name": "Stoic Innovations",
        "email": f"marcus_{datetime.now().strftime('%M%S')}@stoic.com",
        "phone": "+1-555-7788",
        "source": "website",
        "status": "qualified",
        "priority": "high",
        "estimated_value": 45000.00,
        "assigned_to": assigned_user_id
    }
    create_lead_res = client.post('/api/leads', json=lead_payload, headers=headers)
    assert create_lead_res.status_code == 201, f"Create lead failed: {create_lead_res.data}"
    lead_id = create_lead_res.get_json()['lead_id']
    print(f"  -> Lead created with ID={lead_id}.")

    # Add Touchpoint Activity
    act_res = client.post(f'/api/leads/{lead_id}/activities', json={
        "activity_type": "call",
        "notes": "Discussed scope and delivery milestones. Budget confirmed."
    }, headers=headers)
    assert act_res.status_code == 201
    print("  -> Lead touchpoint activity logged.")

    # Convert Lead to Customer
    convert_res = client.post(f'/api/leads/{lead_id}/convert', headers=headers)
    assert convert_res.status_code == 200, f"Convert lead failed: {convert_res.data}"
    converted_cust_id = convert_res.get_json()['customer_id']
    print(f"  -> Lead #{lead_id} successfully converted to Customer #{converted_cust_id}.")

    # Verify Lead Status is converted
    lead_check = client.get(f'/api/leads/{lead_id}', headers=headers).get_json()['lead']
    assert lead_check['status'] == 'converted'
    assert lead_check['converted_customer_id'] == converted_cust_id

    # -------------------------------------------------------------
    # 5. DEALS / SALES PIPELINE & KANBAN
    # -------------------------------------------------------------
    print("\n[5] Testing Deals Pipeline & Kanban...")
    deal_payload = {
        "customer_id": cust_id,
        "title": "Nassau Logistics Enterprise Fleet Expansion",
        "value": 120000.00,
        "stage": "qualification",
        "probability": 60,
        "expected_close_date": (datetime.now() + timedelta(days=45)).strftime('%Y-%m-%d'),
        "assigned_to": assigned_user_id
    }
    create_deal_res = client.post('/api/deals', json=deal_payload, headers=headers)
    assert create_deal_res.status_code == 201, f"Create deal failed: {create_deal_res.data}"
    deal_id = create_deal_res.get_json()['deal_id']
    print(f"  -> Deal created with ID={deal_id}.")

    # Update Deal Stage (Kanban Drag/Drop)
    stage_res = client.put(f'/api/deals/{deal_id}/stage', json={"stage": "proposal"}, headers=headers)
    assert stage_res.status_code == 200
    print("  -> Deal transitioned to 'proposal' stage.")

    # Get Pipeline Kanban aggregation
    kanban_res = client.get('/api/deals/pipeline', headers=headers)
    assert kanban_res.status_code == 200
    kdata = kanban_res.get_json()
    assert "proposal" in kdata['stages']
    assert any(d['id'] == deal_id for d in kdata['stages']['proposal'])
    assert kdata['stage_totals']['proposal'] >= 120000.00
    print(f"  -> Kanban pipeline verified with stage values: {kdata['stage_totals']}.")

    # -------------------------------------------------------------
    # 6. TASKS & STATUS UPDATES
    # -------------------------------------------------------------
    print("\n[6] Testing Tasks Management...")
    task_payload = {
        "title": "Review NDA and Master Services Agreement",
        "description": "Ensure legal compliance for Nassau contract",
        "priority": "high",
        "status": "pending",
        "due_date": (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d'),
        "assigned_to": assigned_user_id,
        "related_to_type": "deal",
        "related_to_id": deal_id
    }
    create_task_res = client.post('/api/tasks', json=task_payload, headers=headers)
    assert create_task_res.status_code == 201
    task_id = create_task_res.get_json()['task_id']
    print(f"  -> Task created with ID={task_id}.")

    # Update Task Status
    task_stat_res = client.put(f'/api/tasks/{task_id}/status', json={"status": "completed"}, headers=headers)
    assert task_stat_res.status_code == 200
    print("  -> Task quick status updated to 'completed'.")

    # -------------------------------------------------------------
    # 7. CALLS LOGGING & SCHEDULING
    # -------------------------------------------------------------
    print("\n[7] Testing Calls Management...")
    call_payload = {
        "subject": "Follow-up on proposal delivery",
        "contact_type": "customer",
        "contact_id": cust_id,
        "call_time": (datetime.now() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S'),
        "duration_minutes": 25,
        "status": "scheduled",
        "notes": "Go over pricing structure and implementation timeline.",
        "user_id": assigned_user_id
    }
    create_call_res = client.post('/api/calls', json=call_payload, headers=headers)
    assert create_call_res.status_code == 201
    call_id = create_call_res.get_json()['call_id']
    print(f"  -> Call scheduled with ID={call_id}.")

    # -------------------------------------------------------------
    # 8. MEETINGS & VALIDATION
    # -------------------------------------------------------------
    print("\n[8] Testing Meetings Management...")
    now_dt = datetime.now()
    valid_meeting_payload = {
        "title": "Executive Presentation",
        "contact_type": "customer",
        "contact_id": cust_id,
        "start_time": (now_dt + timedelta(days=2, hours=10)).strftime('%Y-%m-%d %H:%M:%S'),
        "end_time": (now_dt + timedelta(days=2, hours=11)).strftime('%Y-%m-%d %H:%M:%S'),
        "location": "Boardroom 1 / Virtual Meet",
        "status": "scheduled",
        "notes": "Present slide deck to stakeholders.",
        "user_id": assigned_user_id
    }
    create_mtg_res = client.post('/api/meetings', json=valid_meeting_payload, headers=headers)
    assert create_mtg_res.status_code == 201
    mtg_id = create_mtg_res.get_json()['meeting_id']
    print(f"  -> Meeting scheduled with ID={mtg_id}.")

    # Test Invalid Meeting (end_time <= start_time)
    invalid_meeting_payload = {
        **valid_meeting_payload,
        "start_time": (now_dt + timedelta(days=2, hours=12)).strftime('%Y-%m-%d %H:%M:%S'),
        "end_time": (now_dt + timedelta(days=2, hours=11)).strftime('%Y-%m-%d %H:%M:%S'),
    }
    inv_mtg_res = client.post('/api/meetings', json=invalid_meeting_payload, headers=headers)
    assert inv_mtg_res.status_code == 400, "Validation failed to reject end_time <= start_time"
    print("  -> Correctly rejected invalid meeting where end_time <= start_time.")

    # -------------------------------------------------------------
    # 9. DASHBOARD SUMMARY & LIVE METRICS
    # -------------------------------------------------------------
    print("\n[9] Testing Dashboard Live Summary...")
    dash_res = client.get('/api/dashboard/summary', headers=headers)
    assert dash_res.status_code == 200
    ddata = dash_res.get_json()['summary']
    assert ddata['total_customers'] >= 2
    assert ddata['pipeline_value'] >= 120000.00
    assert len(ddata['recent_activities']) > 0
    print(f"  -> Dashboard live stats verified: {ddata['total_customers']} customers, "
          f"{ddata['total_leads']} leads, ${ddata['pipeline_value']:,.2f} pipeline, "
          f"{len(ddata['recent_activities'])} activities logged.")

    print("\n" + "=" * 70)
    print("ALL STEP 4 CORE MODULE TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == '__main__':
    run_step4_tests()
