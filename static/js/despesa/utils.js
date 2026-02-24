(function () {
  window.App = window.App || {};
  window.App.utils = {};

  window.App.utils.formatter = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 2
  });

  window.App.utils.numberFormatter = new Intl.NumberFormat("pt-BR");

  window.App.utils.normalizeText = function (value) {
    return (value || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
  };

  window.App.utils.decodeBuffer = function (buffer) {
    const utf8 = new TextDecoder("utf-8").decode(buffer);
    if (utf8.includes("\uFFFD")) {
      return new TextDecoder("iso-8859-1").decode(buffer);
    }
    return utf8;
  };

  window.App.utils.parseCurrency = function (value) {
    if (!value) return 0;
    const cleaned = value.replace(/\./g, "").replace(/,/g, ".");
    const parsed = Number.parseFloat(cleaned);
    return Number.isNaN(parsed) ? 0 : parsed;
  };

  // Map government function to thematic area
  window.App.utils.getAreaInfo = function (funcao) {
    if (!funcao) return { key: "outros", label: "Outros" };

    const funcaoLower = funcao.toLowerCase();

    // Saúde
    if (funcaoLower.includes("saúde") || funcaoLower.includes("saude") ||
      funcaoLower.includes("hospitalar") || funcaoLower.includes("sanitária")) {
      return { key: "saude", label: "Saúde" };
    }

    // Educação
    if (funcaoLower.includes("educação") || funcaoLower.includes("educacao") ||
      funcaoLower.includes("ensino")) {
      return { key: "educacao", label: "Educação" };
    }

    // Infraestrutura (Urbanismo, Transporte, Habitação)
    if (funcaoLower.includes("urbanismo") || funcaoLower.includes("transporte") ||
      funcaoLower.includes("habitação") || funcaoLower.includes("habitacao") ||
      funcaoLower.includes("saneamento") || funcaoLower.includes("viação")) {
      return { key: "infraestrutura", label: "Infraestrutura" };
    }

    // Assistência Social
    if (funcaoLower.includes("assistência") || funcaoLower.includes("assistencia") ||
      funcaoLower.includes("social")) {
      return { key: "assistencia", label: "Assistência Social" };
    }

    // Administração
    if (funcaoLower.includes("administração") || funcaoLower.includes("administracao") ||
      funcaoLower.includes("legislativa") || funcaoLower.includes("planejamento") ||
      funcaoLower.includes("judiciária")) {
      return { key: "administracao", label: "Administração" };
    }

    // Previdência
    if (funcaoLower.includes("previdência") || funcaoLower.includes("previdencia")) {
      return { key: "previdencia", label: "Previdência" };
    }

    // Cultura e Esporte
    if (funcaoLower.includes("cultura") || funcaoLower.includes("desporto") ||
      funcaoLower.includes("lazer") || funcaoLower.includes("esporte")) {
      return { key: "cultura", label: "Cultura e Esporte" };
    }

    // Economia (Comércio, Indústria, Agricultura)
    if (funcaoLower.includes("comércio") || funcaoLower.includes("comercio") ||
      funcaoLower.includes("indústria") || funcaoLower.includes("industria") ||
      funcaoLower.includes("agricultura") || funcaoLower.includes("trabalho")) {
      return { key: "economia", label: "Economia" };
    }

    // Segurança
    if (funcaoLower.includes("segurança") || funcaoLower.includes("seguranca")) {
      return { key: "seguranca", label: "Segurança" };
    }

    // Energia
    if (funcaoLower.includes("energia")) {
      return { key: "energia", label: "Energia" };
    }

    // Meio Ambiente
    if (funcaoLower.includes("ambiental") || funcaoLower.includes("ambiente")) {
      return { key: "ambiente", label: "Meio Ambiente" };
    }

    // Outros (Encargos Especiais, etc)
    return { key: "outros", label: "Outros" };
  };

  // Map nature of expense code to simplified expense type
  window.App.utils.getTipoGasto = function (naturezaDespesa) {
    if (!naturezaDespesa) return "Outros";

    const codigo = naturezaDespesa.trim();

    // Pessoal (3.1.90.xx - Aplicações Diretas - Pessoal)
    if (codigo.startsWith("3.1.90.01") || // Aposentadorias
      codigo.startsWith("3.1.90.03") || // Pensões
      codigo.startsWith("3.1.90.04") || // Contratação por tempo determinado
      codigo.startsWith("3.1.90.11") || // Vencimentos e vantagens fixas
      codigo.startsWith("3.1.90.13") || // Obrigações patronais
      codigo.startsWith("3.1.90.16") || // Outras despesas variáveis - pessoal civil
      codigo.startsWith("3.1.90.91") || // Sentenças judiciais
      codigo.startsWith("3.1.90.92") || // Despesas de exercícios anteriores
      codigo.startsWith("3.1.90.94") || // Indenizações
      codigo.startsWith("3.1.91") ||    // Aplicação direta decorrente de operação entre órgãos
      codigo.startsWith("3.1.")) {      // Outros códigos de pessoal
      return "Pessoal";
    }

    // Custeio (3.3.90.xx - Outras Despesas Correntes)
    if (codigo.startsWith("3.3.90.14") || // Diárias
      codigo.startsWith("3.3.90.30") || // Material de consumo
      codigo.startsWith("3.3.90.33") || // Passagens e despesas com locomoção
      codigo.startsWith("3.3.90.35") || // Serviços de consultoria
      codigo.startsWith("3.3.90.36") || // Outros serviços de terceiros - PF
      codigo.startsWith("3.3.90.39") || // Outros serviços de terceiros - PJ
      codigo.startsWith("3.3.90.47") || // Obrigações tributárias e contributivas
      codigo.startsWith("3.3.90.48") || // Outros auxílios financeiros
      codigo.startsWith("3.3.90.92") || // Despesas de exercícios anteriores
      codigo.startsWith("3.3.90.93") || // Indenizações e restituições
      codigo.startsWith("3.3.")) {      // Outros códigos de custeio
      return "Custeio";
    }

    // Investimento (4.4.90.xx - Investimentos)
    if (codigo.startsWith("4.4.90.51") || // Obras e instalações
      codigo.startsWith("4.4.90.52") || // Equipamentos e material permanente
      codigo.startsWith("4.4.90.61") || // Aquisição de imóveis
      codigo.startsWith("4.4.")) {      // Outros investimentos
      return "Investimento";
    }

    // Outros (Inversões Financeiras, Amortização, etc)
    return "Outros";
  };

  // Map nature of expense to contextual expense type (5 categories)
  window.App.utils.getTipoDespesa = function (naturezaDespesa) {
    if (!naturezaDespesa) return "Outros";

    const codigo = naturezaDespesa.trim();

    // Pessoal (3.1.xx)
    if (codigo.startsWith("3.1.")) {
      return "Pessoal";
    }

    // Material (3.3.90.30 - Material de consumo, 4.4.90.52 - Material permanente)
    if (codigo.startsWith("3.3.90.30") || codigo.startsWith("4.4.90.52")) {
      return "Material";
    }

    // Serviços (3.3.90.35, 3.3.90.36, 3.3.90.39 - Serviços de terceiros)
    if (codigo.startsWith("3.3.90.35") || // Consultoria
      codigo.startsWith("3.3.90.36") || // Serviços PF
      codigo.startsWith("3.3.90.39") || // Serviços PJ
      codigo.startsWith("3.3.90.14") || // Diárias
      codigo.startsWith("3.3.90.33")) { // Passagens
      return "Serviços";
    }

    // Obras (4.4.90.51)
    if (codigo.startsWith("4.4.90.51")) {
      return "Obras";
    }

    // Equipamentos (4.4.90.52 já coberto em Material, mas manter lógica)
    if (codigo.startsWith("4.4.90.52")) {
      return "Equipamentos";
    }

    // Outros
    return "Outros";
  };

  // Map resource description to origin (4 categories)
  window.App.utils.getOrigemRecurso = function (descricaoRecurso) {
    if (!descricaoRecurso) return "Não Especificado";

    const desc = descricaoRecurso.toLowerCase().trim();

    // Federal
    if (desc.includes("federal") ||
      desc.includes("união") ||
      desc.includes("fpm") ||
      desc.includes("sus") ||
      desc.includes("fnde") ||
      desc.includes("fundeb")) {
      return "Federal";
    }

    // Estadual
    if (desc.includes("estadual") ||
      desc.includes("estado") ||
      desc.includes("icms") ||
      desc.includes("fpex") ||
      desc.includes("ipva")) {
      return "Estadual";
    }

    // Municipal
    if (desc.includes("municipal") ||
      desc.includes("município") ||
      desc.includes("iptu") ||
      desc.includes("iss") ||
      desc.includes("itbi")) {
      return "Municipal";
    }

    // Próprio (recursos ordinários, livres)
    if (desc.includes("próprio") ||
      desc.includes("proprio") ||
      desc.includes("ordinário") ||
      desc.includes("ordinario") ||
      desc.includes("livre")) {
      return "Próprio";
    }

    // Não especificado
    return "Não Especificado";
  };

  // Map department to secretariat/agency (macro grouping)
  window.App.utils.getSecretaria = function (departamento) {
    if (!departamento) return "Outros Órgãos";

    const dept = departamento.toLowerCase().trim();

    // Secretaria de Saúde
    if (dept.includes("saúde") || dept.includes("saude") ||
      dept.includes("hospital") || dept.includes("ubs") ||
      dept.includes("vigilância") || dept.includes("vigilancia") ||
      dept.includes("epidemiologia")) {
      return "Secretaria de Saúde";
    }

    // Secretaria de Educação
    if (dept.includes("educação") || dept.includes("educacao") ||
      dept.includes("escola") || dept.includes("ensino") ||
      dept.includes("creche") || dept.includes("merenda")) {
      return "Secretaria de Educação";
    }

    // Secretaria de Obras/Infraestrutura
    if (dept.includes("obras") || dept.includes("urbanismo") ||
      dept.includes("engenharia") || dept.includes("infraestrutura") ||
      dept.includes("viação") || dept.includes("saneamento") ||
      dept.includes("habitação") || dept.includes("habitacao")) {
      return "Secretaria de Obras";
    }

    // Secretaria de Administração
    if (dept.includes("administração") || dept.includes("administracao") ||
      dept.includes("planejamento") || dept.includes("gestão") ||
      dept.includes("gestao") || dept.includes("recursos humanos") ||
      dept.includes("finanças") || dept.includes("financas")) {
      return "Secretaria de Administração";
    }

    // Câmara Municipal
    if (dept.includes("câmara") || dept.includes("camara") ||
      dept.includes("vereador") || dept.includes("legislativo")) {
      return "Câmara Municipal";
    }

    // Secretaria de Assistência Social
    if (dept.includes("assistência") || dept.includes("assistencia") ||
      dept.includes("social") || dept.includes("cras") ||
      dept.includes("creas")) {
      return "Secretaria de Assistência Social";
    }

    // Secretaria de Cultura
    if (dept.includes("cultura") || dept.includes("esporte") ||
      dept.includes("lazer") || dept.includes("turismo")) {
      return "Secretaria de Cultura e Esporte";
    }

    // Outros Órgãos
    return "Outros Órgãos";
  };

  // Get action area (wrapper for getAreaInfo label)
  window.App.utils.getAreaAtuacao = function (funcao) {
    const areaInfo = window.App.utils.getAreaInfo(funcao);
    return areaInfo ? areaInfo.label : "Outros";
  };
})();