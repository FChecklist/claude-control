#!/usr/bin/env python3
"""
VERIDIAN Prompt Gateway - Raw Chat Pre-Processing Pipeline
============================================================
MAIN ENTRY POINT: python3 /opt/veridian/scripts/prompt_gateway/gateway.py

NOTE: this is a PRE-PROCESSING FILTER, not a task dispatcher. It is a
completely separate program from the real, production task lifecycle
dispatcher at /opt/veridian/scripts/task-gateway.py (submit/start/log/close/
register-automation/status). This module's job ends at producing a
compressed machine_prompt string; that string is then passed as the
--text value to a `task-gateway.py submit` call by the caller -- this
module never calls task-gateway.py itself.

Orchestrates the complete chat processing pipeline:
  1. Receive raw chat input
  2. Generate unique chat ID (VD- namespace, distinct from task-/KE-/INS- ids)
  3. Classify chat (software-driven, not AI)
  4. Remove noise and convert to machine prompt
  5. Manage and prune context
  6. Tag related files with chat ID
  7. Output pruned, machine-ready prompt

ALL processing is done by SOFTWARE (deterministic Python code), NOT by AI.
This reduces input/output token usage by 50%+ before any AI sees the prompt.

Usage:
  # Process a single chat message (stdin):
  echo "Fix the auth error" | python3 gateway.py --mode stdin

  # Process a chat file:
  python3 gateway.py --mode file --input /path/to/chat.json

  # Interactive mode (read from stdin, output to stdout):
  python3 gateway.py --mode interactive

  # As a pipe filter:
  cat chat_input.txt | python3 gateway.py --mode pipe

  # Initialize the system:
  python3 gateway.py --mode init
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Ensure the engine modules are importable
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENGINE_DIR = os.path.join(SCRIPT_DIR, "engine")
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, ENGINE_DIR)

from config import (
    VERIDIAN_BASE as BASE, DATA_DIR, CHATS_DIR, TAGS_DIR, LOGS_DIR,
    CONTEXT_DIR, SNIPPETS_DIR, SNIP_INDEX_FILE, LOG_LEVEL, LOG_FORMAT, LOG_FILE, get_config
)
from engine.id_generator import IDGenerator, FileTagger
from engine.classifier import ChatClassifier
from engine.prompt_engine import PromptEngine
from engine.context_engine import ContextManager
from engine.snip_engine import SnipEngine
from engine import document_engine


# =============================================================================
# LOGGING SETUP
# =============================================================================
def setup_logging(log_file=None):
    """Configure logging for the gateway."""
    log_path = log_file or LOG_FILE
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler(sys.stderr),
        ]
    )
    return logging.getLogger("VERIDIAN")


logger = setup_logging()


# =============================================================================
# TASK GATEWAY CLASS
# =============================================================================
class TaskGateway:
    """
    Central orchestrator for the VERIDIAN Software Engine.
    Coordinates all sub-modules in the chat processing pipeline.
    """

    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir) if base_dir else Path(BASE)

        if base_dir:
            # Explicit override (e.g. --base-dir for testing): derive the same
            # relative layout under it rather than the namespaced config paths.
            data_dir = str(self.base_dir / "data")
            tags_dir = str(self.base_dir / "data" / "tags")
            context_dir = str(self.base_dir / "data" / "context")
            snippets_dir = str(self.base_dir / "snippets")
            snip_index_file = str(self.base_dir / "snippets" / "snip_index.json")
        else:
            # Default: use the real, namespaced prompt_gateway data paths from
            # config.py (/opt/veridian/data/prompt_gateway/...), not bare
            # /opt/veridian/data or /opt/veridian/snippets, so this module never
            # collides with other tools that write under /opt/veridian directly.
            data_dir = DATA_DIR
            tags_dir = TAGS_DIR
            context_dir = CONTEXT_DIR
            snippets_dir = SNIPPETS_DIR
            snip_index_file = SNIP_INDEX_FILE

        # Initialize all engine modules
        self.id_gen = IDGenerator(base_dir=data_dir)
        self.tagger = FileTagger(tags_dir=tags_dir)
        self.classifier = ChatClassifier()
        self.prompt_engine = PromptEngine()
        self.context_mgr = ContextManager(context_dir=context_dir)
        self.snip_engine = SnipEngine(
            snippets_dir=snippets_dir,
            index_file=snip_index_file,
        )

        logger.info("TaskGateway initialized")
        logger.info(f"Base directory: {self.base_dir}")

    def process_chat(self, raw_text: str, role: str = "user",
                     session_id: str = None) -> dict:
        """
        Process a single chat message through the full pipeline.
        
        Args:
            raw_text: The raw chat text from the user
            role: Message role (user/assistant/system)
            session_id: Optional session ID for context grouping
            
        Returns:
            Complete processing result dict.
        """
        pipeline_start = datetime.now(timezone.utc)

        logger.info(f"Processing chat ({len(raw_text)} chars)...")

        # === STEP 1: Generate Chat ID ===
        chat_id = self.id_gen.generate_id()
        logger.info(f"Generated chat ID: {chat_id}")

        # Document-scale input (multi-page structured text: headings, tables,
        # many sections) takes a dedicated path -- see _process_document_chat
        # for why: the single-sentence pipeline below forces one category
        # onto the whole input, caps entities at 5, and runs a template
        # compiler written for one imperative sentence.
        if document_engine.is_document_input(raw_text):
            return self._process_document_chat(raw_text, role, session_id, chat_id, pipeline_start)

        # === STEP 2: Classify (software, not AI) ===
        analysis = self.classifier.full_analysis(raw_text)
        category = analysis["classification"]["category"]
        intent = analysis["intent"]
        confidence = analysis["classification"]["confidence"]
        logger.info(f"Classification: {category} (confidence: {confidence}, intent: {intent})")

        # === STEP 3: Noise Removal + Machine Prompt Conversion ===
        prompt_result = self.prompt_engine.process(raw_text, analysis["classification"])
        cleaned_text = prompt_result["cleaned_text"]
        machine_prompt = prompt_result["machine_prompt"]
        noise_reduction = prompt_result["noise_stats"]["reduction_pct"]
        token_reduction = prompt_result["token_reduction"]["reduction_pct"]
        logger.info(f"Noise reduction: {noise_reduction}% chars, Token reduction: {token_reduction}%")

        # === STEP 4: Get relevant Snippets for prompt building ===
        snippet_assists = self.snip_engine.get_prompt_assist_snippets(
            category=category, intent=intent
        )
        snippet_names = [s["name"] for s in snippet_assists] if snippet_assists else []
        logger.info(f"Found {len(snippet_assists)} relevant snippets: {snippet_names}")

        # === STEP 5: Context Management ===
        context_id = session_id or chat_id
        window = self.context_mgr.get_window(context_id)
        window.add_message(role, raw_text, msg_id=chat_id)
        
        prune_stats = self.context_mgr.prune_and_save(context_id, current_query=raw_text)
        context_messages = prune_stats.get("messages_after", 0) if isinstance(prune_stats, dict) else 0
        
        # Get pruned context text
        pruned_context = window.get_context_text()
        pruned_tokens = prune_stats.get("tokens_after", 0) if isinstance(prune_stats, dict) else 0
        
        logger.info(f"Context: {context_messages} msgs, ~{pruned_tokens} tokens after prune")

        # === STEP 6: Build Final Output ===
        # The final output is the pruned context + machine prompt
        # This is what gets sent to Claude/AI, saving 50%+ tokens
        final_output = self._build_final_output(
            machine_prompt=machine_prompt,
            pruned_context=pruned_context,
            category=category,
            intent=intent,
            chat_id=chat_id,
            entities=analysis.get("entities", []),
            snippet_assists=snippet_assists,
        )

        pipeline_end = datetime.now(timezone.utc)
        processing_ms = (pipeline_end - pipeline_start).total_seconds() * 1000

        result = {
            "chat_id": chat_id,
            "session_id": session_id,
            "classification": {
                "category": category,
                "intent": intent,
                "confidence": confidence,
            },
            "processing": {
                "original_chars": len(raw_text),
                "cleaned_chars": len(cleaned_text),
                "noise_reduction_pct": noise_reduction,
                "original_est_tokens": analysis["estimated_tokens"],
                "machine_prompt": machine_prompt,
                "token_reduction_pct": token_reduction,
                "context_messages": context_messages,
                "context_tokens": pruned_tokens,
                "processing_time_ms": round(processing_ms, 1),
            },
            "entities": analysis.get("entities", []),
            "snippets_used": snippet_names,
            "final_output": final_output,
            "pipeline_timestamp_utc": pipeline_end.isoformat(),
        }

        logger.info(f"Pipeline complete in {processing_ms:.1f}ms. Token reduction: {token_reduction}%")

        # === STEP 7: Save chat record ===
        self._save_chat_record(chat_id, result)

        return result

    def _build_final_output(self, machine_prompt: str, pruned_context: str,
                             category: str, intent: str, chat_id: str,
                             entities: list, snippet_assists: list,
                             entity_cap: Optional[int] = 5) -> str:
        """
        Build the final pruned output that gets sent to Claude/AI.
        This replaces the original noisy chat with a concise, structured prompt.

        entity_cap=5 is the original short-chat-message behavior (a single
        instruction has at most a handful of entities worth referencing
        up front). Document mode passes entity_cap=None: a 50-section
        architecture spec can legitimately carry hundreds of real named
        entities (engines, technologies, numeric requirements), and silently
        truncating to 5 discards the vast majority of the document's content.
        """
        parts = []

        # Header with machine-readable metadata
        parts.append(f"[VERIDIAN:{chat_id}]")
        parts.append(f"[CAT:{category}|INTENT:{intent}]")

        # Entity references (if any)
        if entities:
            ent_list = entities if entity_cap is None else entities[:entity_cap]
            entity_refs = [f"{e['type']}={e['value']}" for e in ent_list]
            parts.append(f"[ENTS:{','.join(entity_refs)}]")

        # Machine prompt (the core instruction)
        parts.append(f"\n{machine_prompt}")

        # Snippet references (if any)
        if snippet_assists:
            snip_names = [s["name"] for s in snippet_assists[:3]]
            parts.append(f"\n[SNIPS:{','.join(snip_names)}]")

        # Pruned context (only high-relevance messages)
        if pruned_context and len(pruned_context) > 10:
            parts.append(f"\n---\n[CONTEXT]\n{pruned_context}")

        return "\n".join(parts)

    def _process_document_chat(self, raw_text: str, role: str, session_id: Optional[str],
                                chat_id: str, pipeline_start) -> dict:
        """
        Document-mode pipeline: parses real structure (headings, tables)
        instead of forcing the input through the single-sentence compiler.

        Differences from process_chat's short-message path, and why:
          - Classification is per-section (classify_document), not one
            category for the whole document -- ChatClassifier.classify()
            picks a single argmax category, which is correct for one
            instruction and wrong for a document spanning CODE, ANALYSIS,
            OPS, and QUERY content simultaneously.
          - machine_prompt is a structural digest (document_engine.
            build_document_digest) that preserves every heading and table
            row verbatim, instead of PromptConverter's single greedy-regex
            template match, which was written for one imperative sentence
            and garbles/truncates anything longer.
          - entities use extract_document_entities (unbounded, plus numeric-
            fact patterns) and are NOT capped at 5 in the final output.
          - the raw document text is NOT added to the context window as a
            literal chat message. CONTEXT_MIN_MESSAGES protects a lone
            message from pruning regardless of size, so an oversized single
            message would otherwise survive untouched in every future turn's
            [CONTEXT] block -- inflating final_output back to ~original size
            and defeating the token-reduction the gateway exists to provide.
            The document's real content already lives in machine_prompt; the
            context window gets a short pointer instead.
        """
        logger.info(f"Processing DOCUMENT ({len(raw_text)} chars)...")

        blocks = document_engine.parse_document(raw_text)
        sections = document_engine.section_breakdown(blocks)

        doc_classification = self.classifier.classify_document(sections)
        category = doc_classification["primary_category"]
        intent = self.classifier.extract_intent(raw_text)
        entities = self.classifier.extract_document_entities(raw_text)
        logger.info(
            f"Document classification: {category} "
            f"(histogram: {doc_classification['category_histogram']}), "
            f"{len(sections)} sections, {len(entities)} entities"
        )

        machine_prompt = document_engine.build_document_digest(blocks)
        cleaned_text = machine_prompt

        original_length = len(raw_text)
        final_length = len(machine_prompt)
        noise_reduction_pct = round((1 - final_length / max(original_length, 1)) * 100, 1)
        token_reduction = self.prompt_engine.prompt_converter.estimate_token_reduction(
            raw_text, machine_prompt
        )
        logger.info(
            f"Document digest: {noise_reduction_pct}% chars, "
            f"Token reduction: {token_reduction['reduction_pct']}%"
        )

        snippet_assists = self.snip_engine.get_prompt_assist_snippets(
            category=category, intent=intent
        )
        snippet_names = [s["name"] for s in snippet_assists] if snippet_assists else []

        context_id = session_id or chat_id
        window = self.context_mgr.get_window(context_id)
        context_placeholder = (
            f"[document submitted: {chat_id}, {len(sections)} sections, "
            f"{original_length} chars -- full content in machine_prompt, not context]"
        )
        window.add_message(role, context_placeholder, msg_id=chat_id)
        prune_stats = self.context_mgr.prune_and_save(context_id, current_query=context_placeholder)
        context_messages = prune_stats.get("messages_after", 0) if isinstance(prune_stats, dict) else 0
        pruned_context = window.get_context_text()
        pruned_tokens = prune_stats.get("tokens_after", 0) if isinstance(prune_stats, dict) else 0

        final_output = self._build_final_output(
            machine_prompt=machine_prompt,
            pruned_context=pruned_context,
            category=category,
            intent=intent,
            chat_id=chat_id,
            entities=entities,
            snippet_assists=snippet_assists,
            entity_cap=None,
        )

        pipeline_end = datetime.now(timezone.utc)
        processing_ms = (pipeline_end - pipeline_start).total_seconds() * 1000

        result = {
            "chat_id": chat_id,
            "session_id": session_id,
            "document_mode": True,
            "classification": {
                "category": category,
                "intent": intent,
                "confidence": None,
                "category_histogram": doc_classification["category_histogram"],
                "section_classifications": doc_classification["section_classifications"],
            },
            "processing": {
                "original_chars": original_length,
                "cleaned_chars": final_length,
                "noise_reduction_pct": noise_reduction_pct,
                "original_est_tokens": len(raw_text.split()),
                "machine_prompt": machine_prompt,
                "token_reduction_pct": token_reduction["reduction_pct"],
                "context_messages": context_messages,
                "context_tokens": pruned_tokens,
                "processing_time_ms": round(processing_ms, 1),
                "sections_detected": len(sections),
            },
            "entities": entities,
            "snippets_used": snippet_names,
            "final_output": final_output,
            "pipeline_timestamp_utc": pipeline_end.isoformat(),
        }

        logger.info(f"Document pipeline complete in {processing_ms:.1f}ms.")
        self._save_chat_record(chat_id, result)
        return result

    def _save_chat_record(self, chat_id: str, result: dict):
        """Save the processing record to disk."""
        chat_file = Path(CHATS_DIR) / f"{chat_id}.json"
        chat_file.parent.mkdir(parents=True, exist_ok=True)
        with open(chat_file, "w") as f:
            json.dump(result, f, indent=2, default=str)

    def tag_files(self, chat_id: str, file_paths: list, metadata: dict = None):
        """Tag files with a chat ID."""
        for fp in file_paths:
            self.tagger.tag_file(chat_id, fp, metadata)

    def get_chat_record(self, chat_id: str) -> dict:
        """Retrieve a previously saved chat record."""
        chat_file = Path(CHATS_DIR) / f"{chat_id}.json"
        if chat_file.exists():
            with open(chat_file, "r") as f:
                return json.load(f)
        return {"error": f"No record found for {chat_id}"}

    def init_system(self):
        """
        Initialize the VERIDIAN system.
        Creates directories, seeds snippets, and validates installation.
        """
        logger.info("Initializing VERIDIAN system...")
        
        # Ensure all directories exist
        dirs = [DATA_DIR, CHATS_DIR, TAGS_DIR, LOGS_DIR, CONTEXT_DIR]
        for d in dirs:
            Path(d).mkdir(parents=True, exist_ok=True)
            logger.info(f"  Created directory: {d}")

        # Seed default snippets
        count = self.snip_engine.seed_defaults()
        logger.info(f"  Seeded {count} default snippets")

        # Verify all modules
        modules = [
            ("ID Generator", self.id_gen),
            ("File Tagger", self.tagger),
            ("Classifier", self.classifier),
            ("Prompt Engine", self.prompt_engine),
            ("Context Manager", self.context_mgr),
            ("Snip Engine", self.snip_engine),
        ]
        for name, module in modules:
            logger.info(f"  Module OK: {name}")

        # Generate a test ID to verify
        test_id = self.id_gen.generate_id()
        logger.info(f"  Test ID generated: {test_id}")

        # Test classification
        test_result = self.classifier.classify("write a python script to parse json")
        logger.info(f"  Test classification: {test_result['category']}")

        logger.info("VERIDIAN system initialized successfully!")

        return {
            "status": "initialized",
            "test_chat_id": test_id,
            "test_classification": test_result,
            "directories_created": [str(d) for d in dirs],
        }


# =============================================================================
# CLI ENTRY POINT
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="VERIDIAN Prompt Gateway - Raw Chat Pre-Processing Pipeline "
                     "(feeds task-gateway.py --text, does not replace it)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  echo "Fix the auth error" | python3 gateway.py --mode stdin
  python3 gateway.py --mode file --input chat.json
  python3 gateway.py --mode init
  python3 gateway.py --mode interactive
        """
    )
    
    parser.add_argument(
        "--mode", "-m",
        choices=["stdin", "file", "interactive", "pipe", "init"],
        default="stdin",
        help="Processing mode (default: stdin)"
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        help="Input file path (for --mode file)"
    )
    parser.add_argument(
        "--session", "-s",
        type=str,
        default=None,
        help="Session ID for context grouping"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Output only the machine prompt (not the full JSON result)"
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default=None,
        help="Override VERIDIAN base directory"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    gateway = TaskGateway(base_dir=args.base_dir)

    # === MODE: INIT ===
    if args.mode == "init":
        result = gateway.init_system()
        if args.output:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)
        else:
            print(json.dumps(result, indent=2))
        return

    # === MODE: FILE ===
    if args.mode == "file":
        if not args.input:
            print("Error: --input required for --mode file", file=sys.stderr)
            sys.exit(1)
        
        with open(args.input, "r") as f:
            input_data = json.load(f)
        
        raw_text = input_data.get("text", input_data.get("message", input_data.get("content", "")))
        role = input_data.get("role", "user")
        session = args.session or input_data.get("session_id")

        result = gateway.process_chat(raw_text, role=role, session_id=session)
        _output_result(result, args)
        return

    # === MODE: STDIN ===
    if args.mode == "stdin":
        raw_text = sys.stdin.read().strip()
        if not raw_text:
            print("Error: No input on stdin", file=sys.stderr)
            sys.exit(1)
        result = gateway.process_chat(raw_text, role="user", session_id=args.session)
        _output_result(result, args)
        return

    # === MODE: PIPE ===
    if args.mode == "pipe":
        for line in sys.stdin:
            raw_text = line.strip()
            if not raw_text:
                continue
            result = gateway.process_chat(raw_text, role="user", session_id=args.session)
            if args.json_only:
                print(result["final_output"])
            else:
                print(result["final_output"])
            print("---")
        return

    # === MODE: INTERACTIVE ===
    if args.mode == "interactive":
        session = args.session or f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        print(f"VERIDIAN Interactive Mode (session: {session})")
        print("Enter chat messages. Type 'exit' or 'quit' to stop.")
        print("=" * 60)
        
        while True:
            try:
                raw_text = input(">>> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            
            if raw_text.lower() in ("exit", "quit"):
                break
            if not raw_text:
                continue
            
            result = gateway.process_chat(raw_text, role="user", session_id=session)
            print(f"\n[ID: {result['chat_id']}]")
            print(f"Category: {result['classification']['category']} | "
                  f"Intent: {result['classification']['intent']}")
            print(f"Token reduction: {result['processing']['token_reduction_pct']}%")
            print(f"Processing time: {result['processing']['processing_time_ms']}ms")
            print(f"\n--- MACHINE PROMPT ---")
            print(result["final_output"])
            print("=" * 60)
        
        print("\nSession ended. Context saved.")
        return


def _output_result(result: dict, args):
    """Output processing result."""
    if args.json_only:
        print(result["final_output"])
    else:
        output = result["final_output"]
        print(output)
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, default=str)
        logger.info(f"Full result saved to: {args.output}")


if __name__ == "__main__":
    main()
