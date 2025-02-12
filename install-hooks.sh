#!/usr/bin/env bash

# Create the pre-commit hook file
cat > .git/hooks/pre-commit << EOL
#!/usr/bin/env bash

# Run the Rye precommit script
rye run precommit

# Check the exit status
if [ $? -ne 0 ]; then
    echo "Rye precommit script failed. Commit aborted."
    exit 1
fi

exit 0
EOL

# Make the hook executable
chmod +x .git/hooks/pre-commit

echo "Pre-commit hook installed successfully."
