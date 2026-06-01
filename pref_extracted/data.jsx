// Shared mock data for all wireframes — based on the real screenshot
window.WF_DATA = {
  todo: [
    { t: "Pagar Eletromega",                      p: "urgente", c: "tarefa", who: "Joaquim",  whoI: "J", date: "27/05", attach: 2, valor: "R$ 4.820,00" },
    { t: "Pagar Prodasp",                         p: "media",   c: "tarefa", who: "Joaquim",  whoI: "J", date: "27/05", attach: 0, valor: "R$ 1.200,00" },
    { t: "Inserir conciliação do mês 04/2026",    p: "media",   c: "tarefa", who: "Marina",   whoI: "M", date: "26/05", attach: 1, valor: "" },
    { t: "Ver questão da cobrança da Transresíduos", p: "media", c: "tarefa", who: "Roberta", whoI: "R", date: "26/05", attach: 0, valor: "" },
    { t: "Checar quais NFs foram pagas para a Traz valor", p: "baixa", c: "tarefa", who: "Marina", whoI: "M", date: "25/05", attach: 3, valor: "" },
    { t: "Empenhar Moisan",                       p: "baixa",   c: "tarefa", who: "Joaquim",  whoI: "J", date: "25/05", attach: 1, valor: "R$ 980,00" },
  ],
  doing: [
    { t: "Conferir folha de pagamento maio",      p: "alta",    c: "tarefa", who: "Roberta",  whoI: "R", date: "27/05", attach: 4, valor: "" },
    { t: "Atualizar planilha de credores",        p: "media",   c: "tarefa", who: "Marina",   whoI: "M", date: "26/05", attach: 0, valor: "" },
  ],
  done: [
    { t: "Empenhar passagem de Ônibus",           p: "urgente", c: "tarefa", who: "Joaquim",  whoI: "J", date: "24/05", attach: 1, valor: "R$ 650,00", done: "25/05" },
    { t: "Fazer ofício para Câmara Municipal",    p: "urgente", c: "tarefa", who: "Roberta",  whoI: "R", date: "23/05", attach: 0, valor: "",          done: "24/05" },
    { t: "Liquidar NF Eletromega",                p: "media",   c: "tarefa", who: "Joaquim",  whoI: "J", date: "22/05", attach: 2, valor: "R$ 4.820,00", done: "23/05" },
    { t: "Enviar relatório DCTFWeb",              p: "baixa",   c: "lembrete", who: "Marina", whoI: "M", date: "20/05", attach: 1, valor: "",          done: "22/05" },
  ],
};

// Priority palette — muted, paper-friendly
window.WF_PRI = {
  urgente: { ink: "#b53737", soft: "#f3d8d8", label: "URGENTE" },
  alta:    { ink: "#cb6a2a", soft: "#f3e0cf", label: "ALTA"    },
  media:   { ink: "#9a7a1d", soft: "#efe2bd", label: "MÉDIA"   },
  baixa:   { ink: "#4e7a5a", soft: "#d6e6da", label: "BAIXA"   },
};

window.WF_AVATARS = {
  J: "#4d6b8a", M: "#8a5a8c", R: "#7a6d4a",
};
