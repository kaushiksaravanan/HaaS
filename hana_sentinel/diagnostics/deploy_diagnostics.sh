#!/bin/bash
# Deploy Diagnostic Scripts to vlgdbzo3
# =======================================

echo "================================================================"
echo "Deploying HANA Diagnostic Scripts to vlgdbzo3"
echo "================================================================"
echo ""

# Create diagnostics directory
echo "Creating /home/zo3adm/diagnostics directory..."
mkdir -p /home/zo3adm/diagnostics

# Copy scripts
echo "Copying diagnostic scripts..."
cp check_hana_processes.sh /home/zo3adm/diagnostics/
cp check_disk.sh /home/zo3adm/diagnostics/
cp check_memory.sh /home/zo3adm/diagnostics/
cp check_userstore.sh /home/zo3adm/diagnostics/
cp check_backups.sh /home/zo3adm/diagnostics/
cp check_system_params.sh /home/zo3adm/diagnostics/

# Make them executable
echo "Making scripts executable..."
chmod +x /home/zo3adm/diagnostics/*.sh

# List installed scripts
echo ""
echo "Installed diagnostic scripts:"
ls -lh /home/zo3adm/diagnostics/

echo ""
echo "================================================================"
echo "Deployment complete!"
echo "================================================================"
echo ""
echo "Test a script manually:"
echo "  bash /home/zo3adm/diagnostics/check_disk.sh"
echo ""
echo "Or use the API endpoint:"
echo "  GET http://10.238.36.146:9999/diagnostics"
echo ""
