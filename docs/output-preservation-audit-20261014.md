# Output preservation audit

Source inspection found several export writers opening destinations in truncating mode without validating output paths against the input files. The release workflow also references version 3.7.2 while pyproject.toml declares 3.7.3. Keep changes on a review branch and use synthetic temporary files to test output collision prevention.
