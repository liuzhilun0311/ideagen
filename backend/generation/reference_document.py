"""Bounded, text-only Word import. Documents are not persisted or sent upstream."""
import io
import zipfile
from xml.etree import ElementTree

from django.http import JsonResponse
from common.api import require_auth, api_error_response

MAX_BYTES = 10 * 1024 * 1024
MAX_XML_BYTES = 8 * 1024 * 1024
MAX_TEXT = 100000
NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_docx(data):
    if len(data) > MAX_BYTES:
        raise ValueError("参考文档不能超过 10 MiB。")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if len(archive.infolist()) > 2000:
                raise ValueError("Word 文档包含过多内容，请拆分后导入。")
            info = archive.getinfo("word/document.xml")
            if info.file_size > MAX_XML_BYTES or info.flag_bits & 1:
                raise ValueError("Word 正文过大或已加密，请拆分或解除密码后导入。")
            with archive.open(info) as stream:
                xml = stream.read(MAX_XML_BYTES + 1)
        if len(xml) > MAX_XML_BYTES:
            raise ValueError("Word 正文过大，请拆分后导入。")
        # Word normally uses UTF-8; reject entity declarations including UTF-16 XML.
        normalized = xml.replace(b"\x00", b"").upper()
        if b"<!DOCTYPE" in normalized or b"<!ENTITY" in normalized:
            raise ValueError("文档包含不支持的 XML 声明。")
        root = ElementTree.fromstring(xml)
        if root.tag != NAMESPACE + "document":
            raise ValueError("文件不是有效的 Word 文档。")
        paragraphs = []
        for paragraph in root.iter(NAMESPACE + "p"):
            parts = []
            for node in paragraph.iter():
                if node.tag == NAMESPACE + "t":
                    parts.append(node.text or "")
                elif node.tag == NAMESPACE + "tab":
                    parts.append("\t")
                elif node.tag in (NAMESPACE + "br", NAMESPACE + "cr"):
                    parts.append("\n")
            text = "".join(parts).strip()
            if text:
                paragraphs.append(text)
        text = "\n\n".join(paragraphs)
        if not text:
            raise ValueError("Word 文档没有可提取的文字；扫描图片需先转换为文字。")
        if len(text) > MAX_TEXT:
            raise ValueError("参考文本超过 100000 字符，请拆分后导入。")
        return text
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError, RuntimeError, NotImplementedError) as error:
        raise ValueError("Word 文档损坏、格式不支持或已加密，请另存为 .docx 后重试。") from error


@require_auth
def import_document(request):
    if request.method != "POST":
        return api_error_response("请求方法不支持", status=405)
    file = request.FILES.get("file")
    if file is None or not file.name.lower().endswith(".docx"):
        return api_error_response("请选择 Word（.docx）文件；旧版 .doc 请先另存为 .docx。", status=400)
    if file.size > MAX_BYTES:
        return api_error_response("参考文档不能超过 10 MiB。", status=400)
    try:
        text = extract_docx(file.read(MAX_BYTES + 1))
        response = JsonResponse({"success": True, "text": text})
        response["Cache-Control"] = "no-store"
        return response
    except (ValueError, OSError) as error:
        return api_error_response(str(error), status=400)
