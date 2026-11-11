import os
import sys

def create_module(module_name):
    # Força tudo para minúsculo para evitar pastas duplicadas com letras maiúsculas
    module_name_lower = module_name.strip().lower()
    module_name_capital = module_name_lower.capitalize()

    # 1. Criar arquivo de rota em app/routes/
    route_dir = "app/routes"
    os.makedirs(route_dir, exist_ok=True)
    route_file = os.path.join(route_dir, f"{module_name_lower}.py")

    route_code = f"""from flask import Blueprint, render_template, request, redirect, url_for
from app import db

{module_name_lower}_bp = Blueprint('{module_name_lower}', __name__, url_prefix='/{module_name_lower}')

@{module_name_lower}_bp.route('/')
def index():
    # Lista de dados simulada por enquanto
    items = []
    return render_template('{module_name_lower}/index.html', items=items)

@{module_name_lower}_bp.route('/novo', methods=['GET', 'POST'])
def novo():
    if request.method == 'POST':
        # Lógica de salvamento aqui
        return redirect(url_for('{module_name_lower}.index'))
    return render_template('{module_name_lower}/form.html')
"""

    if not os.path.exists(route_file):
        with open(route_file, "w", encoding="utf-8") as f:
            f.write(route_code)
        print(f"[+] Rota criada: {route_file}")
    else:
        print(f"[!] Rota {route_file} já existe (não foi sobrescrita).")

    # 2. Criar pasta e templates em app/templates/
    template_dir = f"app/templates/{module_name_lower}"
    os.makedirs(template_dir, exist_ok=True)

    index_html = f"""{{% extends 'base.html' %}}
{{% block content %}}
<div class=\"d-flex justify-content-between align-items-center mb-4\">
    <h2 class=\"fw-bold text-accent\"><i class=\"fa-solid fa-folder-open me-2\"></i>Gerenciar {module_name_capital}</h2>
    <a href=\"{{{{ url_for('{module_name_lower}.novo') }}}}\" class=\"btn btn-primary\"><i class=\"fa-solid fa-plus me-1\"></i> Novo {module_name_capital}</a>
</div>

<div class=\"card p-4 shadow-sm\">
    <p class=\"text-muted mb-0\">Nenhum registro cadastrado em {module_name_lower} ainda.</p>
</div>
{{% endblock %}}
"""

    index_path = os.path.join(template_dir, "index.html")
    if not os.path.exists(index_path):
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(index_html)
        print(f"[+] Template index criado para {module_name_lower}")
    else:
        print(f"[!] Template index.html para {module_name_lower} já existe.")

    form_html = f"""{{% extends 'base.html' %}}
{{% block content %}}
<h2 class=\"fw-bold text-accent mb-4\">Novo {module_name_capital}</h2>
<div class=\"card p-4 shadow-sm col-md-6\">
    <form method=\"POST\">
        <div class=\"mb-3\">
            <label class=\"form-label\">Nome / Descrição</label>
            <input type=\"text\" name=\"nome\" class=\"form-control bg-dark text-light border-secondary\" required>
        </div>
        <button type=\"submit\" class=\"btn btn-primary\"><i class=\"fa-solid fa-save me-1\"></i> Salvar</button>
        <a href=\"{{{{ url_for('{module_name_lower}.index') }}}}\" class=\"btn btn-outline-secondary ms-2\">Cancelar</a>
    </form>
</div>
{{% endblock %}}
"""

    form_path = os.path.join(template_dir, "form.html")
    if not os.path.exists(form_path):
        with open(form_path, "w", encoding="utf-8") as f:
            f.write(form_html)
        print(f"[+] Template form criado para {module_name_lower}")
    else:
        print(f"[!] Template form.html para {module_name_lower} já existe.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        mod = sys.argv[1]
        create_module(mod)
    else:
        print("Uso correto: python cli.py <nome_do_modulo>")