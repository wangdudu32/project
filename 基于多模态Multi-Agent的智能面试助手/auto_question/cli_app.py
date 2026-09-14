import argparse
import sys
import os
import json
import asyncio
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.markdown import Markdown

# Add current directory to path to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.app.agent.graph import app as agent_app

console = Console()

async def process_pdf(pdf_path: str, num_questions: int = 3):
    """
    Process the PDF and generate questions using the Agent
    """
    if not os.path.exists(pdf_path):
        console.print(f"[red]Error: File {pdf_path} not found![/red]")
        return

    console.print(Panel.fit(f"[bold blue]Processing PDF:[/bold blue] {pdf_path}", title="Mini Qwen Auto Question"))

    inputs = {"pdf_path": pdf_path, "num_questions": num_questions}
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task(description="Initializing Agent...", total=None)
            
            progress.update(task, description="Parsing PDF and Analyzing Content...")
            
            result = await agent_app.ainvoke(inputs)
            
            progress.update(task, description="Generating and Reviewing Questions...")
            
        questions = result.get("final_questions", [])
        
        if not questions:
            console.print("[yellow]No questions were generated. Please check the PDF content or try again.[/yellow]")
            return

        console.print(f"\n[bold green]Successfully generated {len(questions)} questions![/bold green]\n")

        for idx, q in enumerate(questions, 1):
            q_text = q.get('question', 'N/A')
            difficulty = q.get('difficulty', 'medium')
            diff_color = "green" if difficulty == "easy" else "yellow" if difficulty == "medium" else "red"
            
            content = f"[bold]Question {idx}[/bold] ([{diff_color}]{difficulty}[/{diff_color}])\n\n"
            content += f"{q_text}\n\n"
            
            if q.get('type') == 'multiple_choice':
                options = q.get('options', [])
                for opt in options:
                    content += f"- {opt}\n"
            
            content += f"\n[bold cyan]Answer:[/bold cyan] {q.get('answer', 'N/A')}\n"
            content += f"[bold cyan]Analysis:[/bold cyan] {q.get('analysis', 'N/A')}\n"
            
            if 'verification' in q:
                v = q['verification']
                v_status = "[green]PASS[/green]" if v.get('valid') else "[red]FAIL[/red]"
                content += f"\n[bold magenta]Math Verification:[/bold magenta] {v_status}"
                if v.get('valid'):
                    content += f" (Verified equations: {', '.join(v.get('verified_equations', []))})"

            console.print(Panel(content, border_style="blue"))
            console.print("\n")
            
    except Exception as e:
        console.print(f"[bold red]An error occurred:[/bold red] {str(e)}")
        import traceback
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description="Mini Qwen Auto Question CLI")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--num", type=int, default=3, help="Number of questions to generate (default: 3)")
    
    args = parser.parse_args()
    
    # Run async main loop
    asyncio.run(process_pdf(args.pdf_path, args.num))

if __name__ == "__main__":
    main()
