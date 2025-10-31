@echo off
echo ======================================================================
echo Starting ngrok tunnel for Hivemind MCP Server
echo ======================================================================
echo.
echo This will create an HTTPS URL for your local server on port 8080
echo.
echo Make sure your hivemind server is running first!
echo   python src/remote_mcp_server.py
echo.
echo ======================================================================
echo.

ngrok http 8080
