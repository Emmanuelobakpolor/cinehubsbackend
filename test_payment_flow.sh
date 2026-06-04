#!/bin/bash
# Payment Flow Critical Path Test Script
# Tests the complete payment flow: initiate -> verify -> subscription activation
#
# Usage:
#   ./test_payment_flow.sh <base_url> <access_token> <plan_id>
#   Example: ./test_payment_flow.sh http://localhost:8000 "eyJ0eXAi..." 1
#
# For Railway: ./test_payment_flow.sh https://your-app.up.railway.app "your_token" 1

BASE_URL="${1:-http://localhost:8000}"
TOKEN="${2:-}"
PLAN_ID="${3:-1}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${YELLOW}[INFO]${NC} $1"; }
log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; }

# Check dependencies
check_deps() {
    local deps=("curl" "jq")
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            echo -e "${RED}[ERROR]${NC} $dep is required but not installed."
            exit 1
        fi
    done
}

# Test 1: Initialize Payment
test_initiate_payment() {
    log_info "Test 1: Initiating payment for plan $PLAN_ID..."

    local response
    response=$(curl -s -X POST "$BASE_URL/api/payments/initiate/" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"plan_id\": $PLAN_ID}")

    echo "$response" | jq . 2>/dev/null || echo "$response"

    # Extract tx_ref
    TX_REF=$(echo "$response" | jq -r '.tx_ref')
    PAYMENT_LINK=$(echo "$response" | jq -r '.payment_link')

    if [[ "$TX_REF" != "null" && -n "$TX_REF" ]]; then
        log_pass "Payment initiated successfully. tx_ref: $TX_REF"
        echo "TX_REF=$TX_REF" >> test_payment.env
        return 0
    else
        log_fail "Failed to initiate payment"
        return 1
    fi
}

# Test 2: Verify Payment
test_verify_payment() {
    log_info "Test 2: Verifying payment..."

    # Load tx_ref from previous test
    if [[ -f test_payment.env ]]; then
        source test_payment.env
    fi

    if [[ -z "$TX_REF" ]]; then
        log_fail "No TX_REF found. Run initiate test first."
        return 1
    fi

    local response
    response=$(curl -s -X POST "$BASE_URL/api/payments/verify/" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"tx_ref\": \"$TX_REF\", \"transaction_id\": \"TEST-123\"}")

    echo "$response" | jq . 2>/dev/null || echo "$response"

    if echo "$response" | jq -e '.message' > /dev/null 2>&1; then
        log_pass "Payment verified successfully"
        return 0
    else
        log_fail "Failed to verify payment"
        return 1
    fi
}

# Test 3: Check Subscription
test_subscription_active() {
    log_info "Test 3: Checking subscription status..."

    local response
    response=$(curl -s -X GET "$BASE_URL/api/subscriptions/my/" \
        -H "Authorization: Bearer $TOKEN")

    echo "$response" | jq . 2>/dev/null || echo "$response"

    local status
    status=$(echo "$response" | jq -r '.[0].status' 2>/dev/null)

    if [[ "$status" == "ACTIVE" ]]; then
        log_pass "Subscription is ACTIVE"
        return 0
    else
        log_fail "Subscription status: $status (expected ACTIVE)"
        return 1
    fi
}

# Test 4: Idempotency - Verify again should not duplicate
test_idempotency() {
    log_info "Test 4: Testing idempotency (verify same payment again)..."

    if [[ -f test_payment.env ]]; then
        source test_payment.env
    fi

    if [[ -z "$TX_REF" ]]; then
        log_fail "No TX_REF found. Run initiate test first."
        return 1
    fi

    local response
    response=$(curl -s -X POST "$BASE_URL/api/payments/verify/" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"tx_ref\": \"$TX_REF\", \"transaction_id\": \"TEST-123\"}")

    echo "$response" | jq . 2>/dev/null || echo "$response"

    if echo "$response" | jq -e '.message | contains("already")' > /dev/null 2>&1; then
        log_pass "Idempotency check passed - payment already processed"
        return 0
    else
        log_fail "Idempotency check failed"
        return 1
    fi
}

# Test 5: Webhook endpoint exists
test_webhook_exists() {
    log_info "Test 5: Testing webhook endpoint..."

    local response
    response=$(curl -s -X POST "$BASE_URL/api/payments/webhook/flutterwave/" \
        -H "Content-Type: application/json" \
        -d '{"event": "payment.completed", "data": {"tx_ref": "TEST", "status": "successful"}}')

    echo "$response" | jq . 2>/dev/null || echo "$response"

    if echo "$response" | jq -e '.status' > /dev/null 2>&1; then
        log_pass "Webhook endpoint responds correctly"
        return 0
    else
        log_fail "Webhook endpoint not responding"
        return 1
    fi
}

# Run all tests
run_all_tests() {
    echo "========================================"
    echo "Payment Flow Critical Path Tests"
    echo "Base URL: $BASE_URL"
    echo "========================================"
    echo ""

    check_deps

    local failed=0

    test_initiate_payment || ((failed++))
    echo ""

    test_verify_payment || ((failed++))
    echo ""

    test_subscription_active || ((failed++))
    echo ""

    test_idempotency || ((failed++))
    echo ""

    test_webhook_exists || ((failed++))
    echo ""

    echo "========================================"
    if [[ $failed -eq 0 ]]; then
        log_pass "All tests passed!"
        return 0
    else
        log_fail "$failed test(s) failed"
        return 1
    fi
}

# Main
case "${4:-run}" in
    initiate)
        test_initiate_payment
        ;;
    verify)
        test_verify_payment
        ;;
    subscription)
        test_subscription_active
        ;;
    idempotency)
        test_idempotency
        ;;
    webhook)
        test_webhook_exists
        ;;
    run|*)
        run_all_tests
        ;;
esac