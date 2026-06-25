"""
Warning system for dangerous command execution with user confirmation
"""


class WarningSystem:
    """Manages warnings and user confirmation for dangerous commands"""
    
    def __init__(self):
        """Initialize warning system"""
        self.confirmed_commands = set()  # Cache for user-confirmed commands
    
    def should_warn(self, safety_level: str) -> bool:
        """
        Determine if a warning should be shown before execution
        
        Args:
            safety_level: The safety level of the command ('safe', 'moderate', 'dangerous')
            
        Returns:
            True if warning should be shown, False otherwise
        """
        return safety_level in ['moderate', 'dangerous']
    
    def show_warning_and_confirm(self, command: str, reason: str, safety_level: str) -> bool:
        """
        Show warning message and ask user for permission to execute
        
        Args:
            command: The command to be executed
            reason: Explanation of why it's dangerous
            safety_level: The safety level ('safe', 'moderate', 'dangerous')
            
        Returns:
            True if user confirms execution, False otherwise
        """
        # Map safety levels to display colors/symbols
        warning_symbols = {
            'moderate': '⚠️',
            'dangerous': '🛑',
            'safe': '✓'
        }
        
        warning_titles = {
            'moderate': 'MODERATE RISK',
            'dangerous': 'DANGEROUS OPERATION',
            'safe': 'SAFE COMMAND'
        }
        
        symbol = warning_symbols.get(safety_level, '⚠️')
        title = warning_titles.get(safety_level, 'WARNING')
        
        print(f"\n{symbol} {title}")
        print(f"{'=' * 60}")
        print(f"Command: {command}")
        print(f"Reason:  {reason}")
        print(f"{'=' * 60}")
        
        if safety_level == 'dangerous':
            print("\n⛔ This is a DANGEROUS command that could cause harm to your system!")
            print("Please review carefully before proceeding.\n")
        elif safety_level == 'moderate':
            print("\n⚠️ This command modifies files or system state.")
            print("It will execute directly on your host system.\n")
        
        # Get user confirmation
        while True:
            response = input("Do you want to proceed? (yes/no): ").strip().lower()
            if response in ['yes', 'y']:
                print("✓ Command execution approved.\n")
                return True
            elif response in ['no', 'n']:
                print("✗ Command execution cancelled.\n")
                return False
            else:
                print("Please answer 'yes' or 'no': ", end='')
    
    def show_info_message(self, command: str, reason: str) -> None:
        """
        Show informational message for safe commands (no confirmation needed)
        
        Args:
            command: The command being executed
            reason: Description of what it does
        """
        print(f"\n✓ SAFE COMMAND")
        print(f"Command: {command}")
        print(f"Note: {reason}\n")
