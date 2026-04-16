#!/bin/bash

CONTAINER_NAME="h3-dash-server"
INTERFACE="eth0"

function log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] $1"
}

function log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] $1" >&2
}

function reset_network() {
    log "Resetting network rules for ${CONTAINER_NAME}..."
    if docker exec --privileged ${CONTAINER_NAME} tc qdisc del dev ${INTERFACE} root 2>/dev/null; then
        log "Network has been reset to default (unlimited)."
    else
        log "Network was already at default state or reset failed (this is often normal if no rules existed)."
    fi
}

function apply_network() {
    PROFILE=$1
    BW=$2
    LATENCY=$3
    LOSS=$4

    log "Applying Profile: ${PROFILE}"
    log "  - Bandwidth: ${BW}"
    log "  - Latency: ${LATENCY}"
    log "  - Loss: ${LOSS}"

    # Reset first to clear existing rules
    log "  -> Clearing existing rules..."
    docker exec --privileged ${CONTAINER_NAME} tc qdisc del dev ${INTERFACE} root 2>/dev/null

    # Using a hierarchical approach: Root qdisc is HTB (Hierarchical Token Bucket) for BW 
    # and its child is Netem for Delay/Loss
    
    log "  -> Executing: tc qdisc add root handle 1: htb"
    if ! docker exec --privileged ${CONTAINER_NAME} tc qdisc add dev ${INTERFACE} root handle 1: htb default 1; then
        log_error "Failed to add root htb qdisc"
    fi
    
    log "  -> Executing: tc class add rate ${BW}"
    if ! docker exec --privileged ${CONTAINER_NAME} tc class add dev ${INTERFACE} parent 1: classid 1:1 htb rate ${BW}; then
        log_error "Failed to add htb class"
    fi
    
    log "  -> Executing: tc qdisc add netem delay ${LATENCY} loss ${LOSS}"
    if ! docker exec --privileged ${CONTAINER_NAME} tc qdisc add dev ${INTERFACE} parent 1:1 handle 10: netem delay ${LATENCY} loss ${LOSS}; then
        log_error "Failed to add netem qdisc"
    fi
    
    # Notify the web app
    log "  -> Updating profile file..."
    echo "${PROFILE}" > ./html/network_profile.txt
    
    log "Successfully applied ${PROFILE} kịch bản thực nghiệm."
}

case "$1" in
    2g)
        apply_network "2G (GPRS)" "250kbit" "500ms" "2%"
        ;;
    3g)
        apply_network "3G" "2mbit" "100ms" "1%"
        ;;
    4g)
        apply_network "4G (LTE)" "20mbit" "30ms" "0.1%"
        ;;
    5g)
        apply_network "5G" "200mbit" "10ms" "0%"
        ;;
    wifi)
        reset_network
        echo "WiFi" > ./html/network_profile.txt
        log "Applied Actual WiFi (Unlimited bandwidth)"
        ;;
    reset)
        reset_network
        echo "None" > ./html/network_profile.txt
        ;;
    *)
        echo "Sử dụng: $0 {2g|3g|4g|lte|wifi|5g|reset}"
        echo "2G: 250Kbps, 500ms, 2% loss"
        echo "3G: 2Mbps, 100ms, 1% loss"
        echo "4G/LTE: 20Mbps, 30ms, 0.1% loss"
        echo "WIFI: 100Mbps, 15ms, 0.1% loss"
        echo "5G: 200Mbps, 10ms, 0% loss"
        exit 1
esac
