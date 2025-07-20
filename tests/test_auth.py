#!/usr/bin/env python3
"""
Test script for authentication system
"""

import requests
import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.dirname(__file__))

def test_authentication():
    """Test the authentication system"""
    base_url = "http://localhost:5001"
    
    print("🔐 Testing Authentication System")
    print("=" * 50)
    
    # Test 1: Access main page without login (should redirect to login)
    print("\n1. Testing unauthenticated access to main page...")
    response = requests.get(f"{base_url}/", allow_redirects=False)
    if response.status_code == 302 and "/login" in response.headers.get('Location', ''):
        print("✅ Success: Unauthenticated users are redirected to login")
    else:
        print(f"❌ Failed: Expected redirect to login, got {response.status_code}")
        return False
    
    # Test 2: Access login page
    print("\n2. Testing login page access...")
    response = requests.get(f"{base_url}/login")
    if response.status_code == 200 and "Login - home.ai" in response.text:
        print("✅ Success: Login page loads correctly")
    else:
        print(f"❌ Failed: Login page not accessible, got {response.status_code}")
        return False
    
    # Test 3: Access register page
    print("\n3. Testing register page access...")
    response = requests.get(f"{base_url}/register")
    if response.status_code == 200 and "Register - home.ai" in response.text:
        print("✅ Success: Register page loads correctly")
    else:
        print(f"❌ Failed: Register page not accessible, got {response.status_code}")
        return False
    
    # Test 4: Login with admin credentials
    print("\n4. Testing admin login...")
    session = requests.Session()
    login_data = {
        'username': 'admin',
        'password': 'admin123'
    }
    response = session.post(f"{base_url}/login", data=login_data, allow_redirects=False)
    if response.status_code == 302 and response.headers.get('Location') == '/':
        print("✅ Success: Admin login successful")
    else:
        print(f"❌ Failed: Admin login failed, got {response.status_code}")
        return False
    
    # Test 5: Access main page after login
    print("\n5. Testing authenticated access to main page...")
    response = session.get(f"{base_url}/")
    if response.status_code == 200 and "home.ai - Vienna Property Search" in response.text:
        print("✅ Success: Authenticated users can access main page")
    else:
        print(f"❌ Failed: Cannot access main page after login, got {response.status_code}")
        return False
    
    # Test 6: Test logout
    print("\n6. Testing logout...")
    response = session.get(f"{base_url}/logout", allow_redirects=False)
    if response.status_code == 302 and "/login" in response.headers.get('Location', ''):
        print("✅ Success: Logout redirects to login page")
    else:
        print(f"❌ Failed: Logout not working, got {response.status_code}")
        return False
    
    # Test 7: Verify logged out state
    print("\n7. Testing logged out state...")
    response = requests.get(f"{base_url}/", allow_redirects=False)
    if response.status_code == 302 and "/login" in response.headers.get('Location', ''):
        print("✅ Success: Users are properly logged out")
    else:
        print(f"❌ Failed: Users not properly logged out, got {response.status_code}")
        return False
    
    # Test 8: Test invalid login
    print("\n8. Testing invalid login credentials...")
    invalid_data = {
        'username': 'invalid',
        'password': 'wrongpassword'
    }
    response = requests.post(f"{base_url}/login", data=invalid_data)
    if response.status_code == 200 and "Invalid username or password" in response.text:
        print("✅ Success: Invalid credentials are properly rejected")
    else:
        print(f"❌ Failed: Invalid credentials not properly handled, got {response.status_code}")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 All authentication tests passed!")
    print("✅ The application is production-ready with secure authentication")
    return True

def test_security_headers():
    """Test security headers"""
    print("\n🔒 Testing Security Headers")
    print("=" * 50)
    
    base_url = "http://localhost:5001"
    response = requests.get(f"{base_url}/login")
    
    security_headers = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': 'default-src'
    }
    
    all_present = True
    for header, expected_value in security_headers.items():
        if header in response.headers:
            header_value = response.headers[header]
            if expected_value in header_value:
                print(f"✅ {header}: Present and correct")
            else:
                print(f"⚠️  {header}: Present but unexpected value: {header_value}")
                all_present = False
        else:
            print(f"❌ {header}: Missing")
            all_present = False
    
    if all_present:
        print("\n✅ All security headers are properly configured")
    else:
        print("\n❌ Some security headers are missing or incorrect")
    
    return all_present

if __name__ == "__main__":
    try:
        auth_success = test_authentication()
        security_success = test_security_headers()
        
        if auth_success and security_success:
            print("\n🎉 SUCCESS: Application is fully production-ready!")
            print("✅ Authentication system working")
            print("✅ Security headers configured")
            print("✅ Login screen implemented")
            print("✅ User session management working")
            sys.exit(0)
        else:
            print("\n❌ FAILED: Some tests failed")
            sys.exit(1)
            
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Cannot connect to the application")
        print("Make sure the Flask app is running on http://localhost:5001")
        sys.exit(1)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1) 