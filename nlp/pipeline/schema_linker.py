from pipeline.semantic_layer import SemanticLayer


class SchemaLinker:
    def __init__(self, semantic_layer: SemanticLayer):
        self.semantic_layer = semantic_layer

    def link(self, question: str) -> str:
        del question  # full injection at this scope; retrieval path is future work
        return self.semantic_layer.render_ddl()
