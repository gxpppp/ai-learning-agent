"""Tool adapter — wrap existing 14 tools as OpenHarness BaseTool subclasses."""

from __future__ import annotations

import json
import logging
from typing import Any

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
from openharness.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# ─── Pydantic input models ───

# Lazy-loaded to avoid import overhead
try:
    from pydantic import BaseModel, Field
except ImportError:
    BaseModel = object  # type: ignore
    Field = None  # type: ignore


def _make_field(description: str, default: Any = None) -> Any:
    return Field(description=description, default=default)


# ─── Base adapter for all vault tools ───


class _VaultTool(BaseTool):
    """Base class for tools that operate on the Obsidian vault."""

    async def execute(self, arguments: Any, context: ToolExecutionContext) -> ToolResult:
        vault_path = context.metadata.get("vault_path", str(context.cwd))
        try:
            result = await self._do_execute(arguments, vault_path, context)
            return ToolResult(output=result)
        except Exception as exc:
            logger.exception(f"Tool {self.name} failed")
            return ToolResult(output=json.dumps({"error": str(exc)}), is_error=True)

    async def _do_execute(self, args: Any, vault_path: str, ctx: ToolExecutionContext) -> str:
        raise NotImplementedError


# ─── Read-only tools ───


class SearchNotesInput(BaseModel):
    query: str = Field(description="Search query")
    top_k: int = Field(default=5, description="Number of results")


class SearchNotesTool(_VaultTool):
    name = "search_notes"
    description = "Semantic search the Obsidian vault for notes matching a query"
    input_model = SearchNotesInput

    async def _do_execute(self, args: SearchNotesInput, vault_path: str, ctx: ToolExecutionContext) -> str:
        from app.core.tool_registry import execute_tool
        return await execute_tool("search_notes", {"query": args.query, "top_k": args.top_k}, vault_path)


class ReadNoteInput(BaseModel):
    note_path: str = Field(description="Path to the note relative to vault root")


class ReadNoteTool(_VaultTool):
    name = "read_note"
    description = "Read the full content of a note in the vault"
    input_model = ReadNoteInput

    async def _do_execute(self, args: ReadNoteInput, vault_path: str, ctx: ToolExecutionContext) -> str:
        from app.core.tool_registry import execute_tool
        return await execute_tool("read_note", {"note_path": args.note_path}, vault_path)


class ListFolderInput(BaseModel):
    path: str = Field(default="", description="Folder path relative to vault root")


class ListFolderTool(_VaultTool):
    name = "list_folder"
    description = "List contents of a folder in the vault"
    input_model = ListFolderInput

    async def _do_execute(self, args: ListFolderInput, vault_path: str, ctx: ToolExecutionContext) -> str:
        from app.core.tool_registry import execute_tool
        return await execute_tool("list_folder", {"path": args.path}, vault_path)


class SuggestTagsInput(BaseModel):
    note_path: str = Field(description="Path to the note")
    max_tags: int = Field(default=5, description="Max number of tags")


class SuggestTagsTool(_VaultTool):
    name = "suggest_tags"
    description = "Suggest frontmatter tags for a note based on its content"
    input_model = SuggestTagsInput

    async def _do_execute(self, args: SuggestTagsInput, vault_path: str, ctx: ToolExecutionContext) -> str:
        from app.core.tool_registry import execute_tool
        return await execute_tool("suggest_tags", {"note_path": args.note_path, "max_tags": args.max_tags}, vault_path)


class RecommendLinksInput(BaseModel):
    note_path: str = Field(description="Path to the note")
    max_links: int = Field(default=5, description="Max number of links")


class RecommendLinksTool(_VaultTool):
    name = "recommend_links"
    description = "Recommend bidirectional wiki links between notes"
    input_model = RecommendLinksInput

    async def _do_execute(self, args: RecommendLinksInput, vault_path: str, ctx: ToolExecutionContext) -> str:
        from app.core.tool_registry import execute_tool
        return await execute_tool("recommend_links", {"note_path": args.note_path, "max_links": args.max_links}, vault_path)


# ─── Write tools (full-access only) ───


class CreateNoteInput(BaseModel):
    folder: str = Field(description="Target folder relative to vault root")
    filename: str = Field(description="Filename with .md extension")
    content: str = Field(description="Markdown content")
    tags: list[str] = Field(default_factory=list, description="Frontmatter tags")


class CreateNoteTool(_VaultTool):
    name = "create_note"
    description = "Create a new Markdown note in the vault"
    input_model = CreateNoteInput

    async def _do_execute(self, args: CreateNoteInput, vault_path: str, ctx: ToolExecutionContext) -> str:
        from app.core.tool_registry import execute_tool
        return await execute_tool("create_note", {
            "folder": args.folder, "filename": args.filename,
            "content": args.content, "tags": args.tags,
        }, vault_path)


class UpdateNoteInput(BaseModel):
    note_path: str = Field(description="Path to the note")
    content: str = Field(description="New Markdown content")


class UpdateNoteTool(_VaultTool):
    name = "update_note"
    description = "Update the content of an existing note"
    input_model = UpdateNoteInput

    async def _do_execute(self, args: UpdateNoteInput, vault_path: str, ctx: ToolExecutionContext) -> str:
        from app.core.tool_registry import execute_tool
        return await execute_tool("update_note", {"note_path": args.note_path, "content": args.content}, vault_path)


class DeleteNoteInput(BaseModel):
    note_path: str = Field(description="Path to the note to delete")


class DeleteNoteTool(_VaultTool):
    name = "delete_note"
    description = "Delete a note (moved to .trash/)"
    input_model = DeleteNoteInput

    async def _do_execute(self, args: DeleteNoteInput, vault_path: str, ctx: ToolExecutionContext) -> str:
        from app.core.tool_registry import execute_tool
        return await execute_tool("delete_note", {"note_path": args.note_path}, vault_path)


class CreateFolderInput(BaseModel):
    path: str = Field(description="Folder path relative to vault root")


class CreateFolderTool(_VaultTool):
    name = "create_folder"
    description = "Create a folder in the vault"
    input_model = CreateFolderInput

    async def _do_execute(self, args: CreateFolderInput, vault_path: str, ctx: ToolExecutionContext) -> str:
        from app.core.tool_registry import execute_tool
        return await execute_tool("create_folder", {"path": args.path}, vault_path)


class MoveNoteInput(BaseModel):
    source: str = Field(description="Current note path")
    destination: str = Field(description="New note path")


class MoveNoteTool(_VaultTool):
    name = "move_note"
    description = "Move or rename a note"
    input_model = MoveNoteInput

    async def _do_execute(self, args: MoveNoteInput, vault_path: str, ctx: ToolExecutionContext) -> str:
        from app.core.tool_registry import execute_tool
        return await execute_tool("move_note", {"source": args.source, "destination": args.destination}, vault_path)


class OcrDocumentInput(BaseModel):
    file_path: str = Field(default="", description="Absolute path to image/PDF file")
    image_path: str = Field(default="", description="Path to image/PDF file (alias)")
    output_folder: str = Field(default="OCR", description="Folder to save result")


class OcrDocumentTool(_VaultTool):
    name = "ocr_document"
    description = "Extract text from an image or PDF using OCR"
    input_model = OcrDocumentInput

    async def _do_execute(self, args: OcrDocumentInput, vault_path: str, ctx: ToolExecutionContext) -> str:
        from app.core.tool_registry import execute_tool
        path = args.file_path or args.image_path
        return await execute_tool("ocr_document", {
            "file_path": path, "output_folder": args.output_folder,
        }, vault_path)


class ClassifyNoteInput(BaseModel):
    note_path: str = Field(description="Path to the note")


class ClassifyNoteTool(_VaultTool):
    name = "classify_note"
    description = "Classify a note by content type"
    input_model = ClassifyNoteInput

    async def _do_execute(self, args: ClassifyNoteInput, vault_path: str, ctx: ToolExecutionContext) -> str:
        from app.core.tool_registry import execute_tool
        return await execute_tool("classify_note", {"note_path": args.note_path}, vault_path)


class GenerateSummaryInput(BaseModel):
    note_path: str = Field(description="Path to the note")


class GenerateSummaryTool(_VaultTool):
    name = "generate_summary"
    description = "Generate a TL;DR summary of a note and append it"
    input_model = GenerateSummaryInput

    async def _do_execute(self, args: GenerateSummaryInput, vault_path: str, ctx: ToolExecutionContext) -> str:
        from app.core.tool_registry import execute_tool
        return await execute_tool("generate_summary", {"note_path": args.note_path}, vault_path)


class GetVaultStatusInput(BaseModel):
    pass


class GetVaultStatusTool(_VaultTool):
    name = "get_vault_status"
    description = "Check vault indexing and word cloud status"
    input_model = GetVaultStatusInput

    async def _do_execute(self, args: GetVaultStatusInput, vault_path: str, ctx: ToolExecutionContext) -> str:
        from app.core.tool_registry import execute_tool
        return await execute_tool("get_vault_status", {}, vault_path)


class WebSearchInput(BaseModel):
    query: str = Field(description="Search query")
    max_results: int = Field(default=5, description="Max results")


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web using Tavily for current information"
    input_model = WebSearchInput

    async def execute(self, arguments: WebSearchInput, context: ToolExecutionContext) -> ToolResult:
        try:
            from app.llm.search import search_web
            results = await search_web(arguments.query, arguments.max_results)
            formatted = "\n".join(
                f"- [{r.title}]({r.url}): {r.content[:200]}" for r in results
            ) if results else "No web results found."
            return ToolResult(output=formatted)
        except Exception as exc:
            return ToolResult(output=f"Web search error: {exc}", is_error=True)


# ─── Registry ───

def create_vault_tool_registry() -> ToolRegistry:
    """Create a tool registry with all 15 vault tools registered."""
    registry = ToolRegistry()
    # Read-only
    registry.register(SearchNotesTool())
    registry.register(ReadNoteTool())
    registry.register(ListFolderTool())
    registry.register(SuggestTagsTool())
    registry.register(RecommendLinksTool())
    # Write
    registry.register(CreateNoteTool())
    registry.register(UpdateNoteTool())
    registry.register(DeleteNoteTool())
    registry.register(CreateFolderTool())
    registry.register(MoveNoteTool())
    registry.register(OcrDocumentTool())
    registry.register(ClassifyNoteTool())
    registry.register(GenerateSummaryTool())
    registry.register(GetVaultStatusTool())
    # Web
    registry.register(WebSearchTool())
    return registry
