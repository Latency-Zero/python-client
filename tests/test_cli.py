"""
Tests for latzero.cli module.
"""

import pytest
from latzero.cli.main import main


class TestCLI:
    """Tests for CLI commands."""
    
    def test_cli_help(self, capsys):
        """Test CLI help output."""
        with pytest.raises(SystemExit) as exc_info:
            main(['--help'])
        # argparse exits with 0 for help
        assert exc_info.value.code == 0
    
    def test_cli_list_empty(self, capsys):
        """Test listing pools when none exist."""
        # This test may show existing pools or "No active pools"
        result = main(['list'])
        assert result == 0
    
    def test_cli_stats(self, capsys):
        """Test stats command."""
        result = main(['stats'])
        assert result == 0
        
        captured = capsys.readouterr()
        assert 'Total pools' in captured.out
    
    def test_cli_stats_json(self, capsys):
        """Test stats command with JSON output."""
        result = main(['stats', '--json'])
        assert result == 0
        
        captured = capsys.readouterr()
        import json
        data = json.loads(captured.out)
        assert 'pool_count' in data
    
    def test_cli_cleanup(self, capsys):
        """Test cleanup command."""
        result = main(['cleanup'])
        assert result == 0
