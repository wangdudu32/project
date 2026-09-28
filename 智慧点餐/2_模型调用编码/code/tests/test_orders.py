from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from api.main import app
from models import LoginSession, MenuItem, Order, User, now
from security import verify_password


def checkout_data():
    return {'request_id': str(uuid4()), 'contact_name': '小明', 'contact_phone': '13800138000',
            'delivery_address': '北京市海淀区中关村一号', 'remark': '少放盐'}


def make_order(buyer):
    assert buyer.put('/cart/1', json={'quantity': 2}).status_code == 200
    assert buyer.put('/cart/3', json={'quantity': 1}).status_code == 200
    response = buyer.post('/orders', json=checkout_data())
    assert response.status_code == 201
    return response.json()


def test_registration_password_cookie_logout(client, db_factory):
    body = {'username': 'Alice', 'password': 'password123'}
    response = client.post('/auth/register', json=body)
    assert response.status_code == 201
    assert response.json()['is_admin'] is False
    assert 'password' not in response.text
    assert 'HttpOnly' in response.headers['set-cookie']
    assert 'SameSite=strict' in response.headers['set-cookie']
    token = client.cookies.get('aimenu_session')
    with db_factory() as db:
        user = db.scalar(select(User).where(User.username == 'alice'))
        assert user.password_hash != body['password']
        assert verify_password(body['password'], user.password_hash)
        assert db.get(LoginSession, token) is None
    assert client.post('/auth/register', json=body).status_code == 409
    assert client.get('/auth/me').status_code == 200
    assert client.post('/auth/logout').status_code == 200
    client.cookies.set('aimenu_session', token)
    assert client.get('/auth/me').status_code == 401
    client.cookies.clear()
    assert client.post('/auth/login', json={**body, 'password': 'wrongpassword'}).status_code == 401
    assert client.post('/auth/login', json=body).status_code == 200


def test_expired_session(buyer, db_factory):
    from datetime import timedelta
    with db_factory() as db:
        for session in db.scalars(select(LoginSession)).all():
            session.expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert buyer.get('/cart').status_code == 401


def test_permissions_and_csrf(client, buyer):
    assert buyer.get('/admin/menu').status_code == 403
    assert buyer.post('/admin/menu', json={}).status_code == 403
    assert buyer.post('/auth/register', json={'username': 'hacker', 'password': 'password123', 'is_admin': True}).status_code == 422
    with TestClient(app) as guest:
        assert guest.get('/cart').status_code == 401
        assert guest.post('/auth/login', json={'username': 'buyer', 'password': 'buyerpass123'}).status_code == 403


@pytest.mark.parametrize('quantity', [-1, 100, 1.5, True, '2'])
def test_cart_validation(buyer, quantity):
    assert buyer.put('/cart/1', json={'quantity': quantity}).status_code == 422


def test_cart_update_remove_and_clear(buyer):
    result = buyer.put('/cart/1', json={'quantity': 2}).json()
    assert result['total_amount'] == '56.00'
    assert buyer.put('/cart/1', json={'quantity': 3}).json()['total_amount'] == '84.00'
    assert buyer.put('/cart/1', json={'quantity': 0}).json()['items'] == []
    assert buyer.put('/cart/999', json={'quantity': 1}).status_code == 409
    buyer.put('/cart/2', json={'quantity': 1})
    assert buyer.delete('/cart').json()['items'] == []
    assert buyer.post('/orders', json=checkout_data()).status_code == 400


def test_order_amount_idempotency_and_snapshot(buyer, db_factory):
    buyer.put('/cart/1', json={'quantity': 2})
    payload = checkout_data()
    assert buyer.post('/orders', json={**payload, 'total_amount': '0.01'}).status_code == 422
    result = buyer.post('/orders', json=payload).json()
    assert result['total_amount'] == '56.00'
    assert result['items'][0]['unit_price'] == '28.00'
    assert buyer.get('/cart').json()['items'] == []
    assert buyer.post('/orders', json=payload).json()['id'] == result['id']
    assert len(buyer.get('/orders').json()) == 1
    with db_factory() as db:
        item = db.get(MenuItem, 1)
        item.price = Decimal('99.00')
        item.dish_name = '新菜名'
        db.commit()
    detail = buyer.get(f"/orders/{result['id']}").json()
    assert detail['items'][0]['dish_name'] == '宫保鸡丁'
    assert detail['total_amount'] == '56.00'


def test_other_users_cannot_access_order_or_cart(buyer):
    order = make_order(buyer)
    with TestClient(app, headers={'X-Requested-With': 'aimenu'}) as other:
        other.post('/auth/register', json={'username': 'other', 'password': 'otherpass123'})
        assert other.get('/cart').json()['items'] == []
        assert other.get('/orders').json() == []
        assert other.get(f"/orders/{order['id']}").status_code == 404
        assert other.post(f"/orders/{order['id']}/pay").status_code == 404
        assert other.post(f"/orders/{order['id']}/cancel").status_code == 404


def test_full_order_lifecycle(buyer, admin):
    order = make_order(buyer)
    order_id = order['id']
    assert order['total_amount'] == '71.00'
    assert admin.patch(f'/admin/orders/{order_id}/status', json={'status': 'preparing'}).status_code == 409
    assert buyer.post(f'/orders/{order_id}/pay').json()['status'] == 'paid'
    assert buyer.post(f'/orders/{order_id}/pay').json()['status'] == 'paid'
    assert buyer.post(f'/orders/{order_id}/cancel').status_code == 409
    assert admin.patch(f'/admin/orders/{order_id}/status', json={'status': 'completed'}).status_code == 409
    for status in ['preparing', 'delivering', 'completed']:
        response = admin.patch(f'/admin/orders/{order_id}/status', json={'status': status})
        assert response.status_code == 200
        assert response.json()['status'] == status
    assert buyer.get(f'/orders/{order_id}').json()['status'] == 'completed'
    assert admin.patch(f'/admin/orders/{order_id}/status', json={'status': 'preparing'}).status_code == 409


def test_cancelled_order_cannot_be_paid(buyer):
    order = make_order(buyer)
    assert buyer.post(f"/orders/{order['id']}/cancel").json()['status'] == 'cancelled'
    assert buyer.post(f"/orders/{order['id']}/cancel").status_code == 200
    assert buyer.post(f"/orders/{order['id']}/pay").status_code == 409


def test_unavailable_dish_rolls_back_checkout(buyer, db_factory):
    buyer.put('/cart/1', json={'quantity': 1})
    with db_factory() as db:
        db.get(MenuItem, 1).is_available = False
        db.commit()
    assert buyer.post('/orders', json=checkout_data()).status_code == 409
    assert buyer.get('/orders').json() == []
    assert len(buyer.get('/cart').json()['items']) == 1
    assert buyer.put('/cart/1', json={'quantity': 0}).status_code == 200


def test_admin_menu_changes(admin, client):
    payload = {'dish_name': '番茄鸡蛋', 'price': '16.50', 'category': '家常菜', 'allergens': '鸡蛋'}
    item = admin.post('/admin/menu', json=payload).json()
    assert item['id'] in [dish['id'] for dish in client.get('/menu/list').json()['menu_items']]
    assert admin.put(f"/admin/menu/{item['id']}", json={**payload, 'is_available': False}).status_code == 200
    assert item['id'] not in [dish['id'] for dish in client.get('/menu/list').json()['menu_items']]
    assert len(admin.get('/admin/menu').json()) == 6
    assert admin.post('/admin/menu', json={**payload, 'price': '0.001'}).status_code == 422


def test_concurrent_checkout_same_request(buyer, db_factory):
    buyer.put('/cart/1', json={'quantity': 1})
    payload = checkout_data()
    cookie = buyer.cookies.get('aimenu_session')
    def submit(_):
        with TestClient(app, headers={'X-Requested-With': 'aimenu', 'Cookie': f'aimenu_session={cookie}'}) as request:
            response = request.post('/orders', json=payload)
            return response.status_code, response.json()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, range(2)))
    assert [result[0] for result in results] == [201, 201]
    assert results[0][1]['id'] == results[1][1]['id']
    with db_factory() as db:
        assert len(db.scalars(select(Order)).all()) == 1


def test_concurrent_pay_and_cancel(buyer):
    order = make_order(buyer)
    cookie = buyer.cookies.get('aimenu_session')
    def act(operation):
        with TestClient(app, headers={'X-Requested-With': 'aimenu', 'Cookie': f'aimenu_session={cookie}'}) as request:
            return request.post(f"/orders/{order['id']}/{operation}").status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(act, ['pay', 'cancel']))
    assert sorted(results) == [200, 409]
    assert buyer.get(f"/orders/{order['id']}").json()['status'] in ['paid', 'cancelled']
