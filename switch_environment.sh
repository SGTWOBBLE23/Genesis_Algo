#!/bin/bash

# Environment switcher for MT5 Genesis trading platform
# This script switches between production and test environments

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Current directory
CURRENT_DIR=$(pwd)
PARENT_DIR=$(dirname "$CURRENT_DIR")
BASE_DIR=$(basename "$CURRENT_DIR")

# Function to save current state to ensure we can restore if needed
save_current_state() {
    echo -e "${BLUE}Saving current state...${NC}"
    timestamp=$(date +%Y%m%d_%H%M%S)
    mkdir -p backups/"$timestamp"
    cp -r *.py templates static models.py mt5_ea_api.py backups/"$timestamp"/ 2>/dev/null
    echo -e "${GREEN}Current state saved to backups/$timestamp${NC}"
}

# Function to switch to production environment
switch_to_production() {
    if [ "$BASE_DIR" = "dev_environment" ]; then
        echo -e "${YELLOW}Currently in test environment. Switching to production...${NC}"
        cd ..
        echo -e "${GREEN}Switched to production environment!${NC}"
        echo -e "Current directory: $(pwd)"
        # Restart the workflow for production
        echo -e "${BLUE}Restarting production server...${NC}"
        echo "To start the production server, run the appropriate workflow."
    else
        echo -e "${GREEN}Already in production environment.${NC}"
        echo -e "Current directory: $(pwd)"
    fi
}

# Function to switch to test environment
switch_to_test() {
    if [ "$BASE_DIR" != "dev_environment" ]; then
        # Check if dev_environment exists
        if [ ! -d "dev_environment" ]; then
            echo -e "${YELLOW}Test environment not found. Creating...${NC}"
            mkdir -p dev_environment
            cp -r *.py templates static models.py mt5_ea_api.py dev_environment/ 2>/dev/null
            echo -e "${GREEN}Test environment created.${NC}"
        fi
        
        echo -e "${YELLOW}Currently in production environment. Switching to test...${NC}"
        cd dev_environment
        echo -e "${GREEN}Switched to test environment!${NC}"
        echo -e "Current directory: $(pwd)"
        # Note about starting test server
        echo -e "${BLUE}To start the test server, run the appropriate workflow in this directory.${NC}"
    else
        echo -e "${GREEN}Already in test environment.${NC}"
        echo -e "Current directory: $(pwd)"
    fi
}

# Main menu
show_menu() {
    echo -e "${BLUE}=== MT5 Genesis Environment Switcher ===${NC}"
    echo -e "${YELLOW}Current environment: ${GREEN}$(if [ "$BASE_DIR" = "dev_environment" ]; then echo "TEST"; else echo "PRODUCTION"; fi)${NC}"
    echo "1. Switch to Production Environment"
    echo "2. Switch to Test Environment"
    echo "3. Save Current State (Backup)"
    echo "4. Exit"
    echo -n "Enter your choice [1-4]: "
    read -r choice
    
    case $choice in
        1) switch_to_production ;;
        2) switch_to_test ;;
        3) save_current_state ;;
        4) echo "Exiting..."; exit 0 ;;
        *) echo -e "${YELLOW}Invalid choice. Please try again.${NC}" ;;
    esac
    
    # Show menu again
    echo ""
    show_menu
}

# Start the menu
show_menu