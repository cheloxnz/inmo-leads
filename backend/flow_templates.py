"""
InmoBot SaaS - Templates de flujo por rubro
Cada template define: pasos del flujo, preguntas, botones, scoring, mensajes
"""

TEMPLATES = {
    "inmobiliaria": {
        "id": "inmobiliaria",
        "name": "Inmobiliaria",
        "description": "Bot para inmobiliarias: compra, alquiler, venta de propiedades",
        "welcome_message": "Hola! Soy el asistente virtual de {business_name}. Estoy aca para ayudarte a encontrar tu propiedad ideal.",
        "welcome_buttons": [
            {"id": "intent_comprar", "title": "Comprar"},
            {"id": "intent_alquilar", "title": "Alquilar"},
            {"id": "intent_vender", "title": "Vender"}
        ],
        "intents": ["comprar", "alquilar", "vender", "inversion"],
        "flow_steps": [
            {
                "id": "intent",
                "question": "Que te interesa?",
                "type": "buttons",
                "buttons": [
                    {"id": "intent_comprar", "title": "Comprar"},
                    {"id": "intent_alquilar", "title": "Alquilar"},
                    {"id": "intent_vender", "title": "Vender"}
                ],
                "field": "intent",
                "use_ai": True,
                "ai_prompt": "Clasifica la intencion del usuario: comprar, alquilar, vender, inversion, sin_definir"
            },
            {
                "id": "name",
                "question": "Como te llamas?",
                "type": "text",
                "field": "name"
            },
            {
                "id": "zone",
                "question": "En que zona estas buscando?",
                "type": "text",
                "field": "custom_fields.zone",
                "use_ai": True,
                "ai_prompt": "Extrae la zona o barrio del mensaje del usuario"
            },
            {
                "id": "budget",
                "question": "Cual es tu presupuesto aproximado?",
                "type": "text",
                "field": "custom_fields.budget",
                "use_ai": True,
                "ai_prompt": "Extrae y normaliza el presupuesto. Ej: '200 lucas' -> 'USD 200.000'",
                "skip_for_intents": ["vender"]
            },
            {
                "id": "property_type",
                "question": "Que tipo de propiedad buscas?",
                "type": "buttons",
                "buttons": [
                    {"id": "tipo_depto", "title": "Departamento"},
                    {"id": "tipo_casa", "title": "Casa"},
                    {"id": "tipo_ph", "title": "PH"}
                ],
                "field": "custom_fields.property_type"
            },
            {
                "id": "bedrooms",
                "question": "Cuantos ambientes necesitas?",
                "type": "buttons",
                "buttons": [
                    {"id": "amb_1", "title": "1 ambiente"},
                    {"id": "amb_2", "title": "2 ambientes"},
                    {"id": "amb_3", "title": "3 o mas"}
                ],
                "field": "custom_fields.bedrooms",
                "skip_for_intents": ["vender"]
            },
            {
                "id": "must_have",
                "question": "Hay algo que sea imprescindible? (balcon, cochera, pileta, etc.)",
                "type": "text",
                "field": "custom_fields.must_have"
            },
            {
                "id": "urgency",
                "question": "Para cuando lo necesitas?",
                "type": "buttons",
                "buttons": [
                    {"id": "urg_urgente", "title": "Urgente (semanas)"},
                    {"id": "urg_mes", "title": "Proximo mes"},
                    {"id": "urg_meses", "title": "Proximos meses"}
                ],
                "field": "urgency"
            },
            {
                "id": "financing",
                "question": "Como pensas financiarlo?",
                "type": "buttons",
                "buttons": [
                    {"id": "fin_efectivo", "title": "Efectivo"},
                    {"id": "fin_credito", "title": "Credito hipotecario"},
                    {"id": "fin_nose", "title": "No se aun"}
                ],
                "field": "custom_fields.financing",
                "skip_for_intents": ["alquilar", "vender"]
            }
        ],
        "scoring": {
            "max_score": 12,
            "criteria": [
                {"field": "custom_fields.budget", "points": 2, "condition": "not_empty"},
                {"field": "custom_fields.zone", "points": 2, "condition": "not_empty"},
                {"field": "custom_fields.property_type", "points": 1, "condition": "not_empty"},
                {"field": "urgency", "points": 3, "condition": "equals", "value": "urgente"},
                {"field": "urgency", "points": 2, "condition": "equals", "value": "proximo_mes"},
                {"field": "urgency", "points": 1, "condition": "equals", "value": "meses"},
                {"field": "custom_fields.financing", "points": 1, "condition": "not_equals", "value": "no_se"},
                {"field": "intent", "points": 1, "condition": "equals", "value": "comprar"},
                {"field": "custom_fields.must_have", "points": 1, "condition": "not_empty"}
            ],
            "hot_threshold": 7,
            "warm_threshold": 4
        },
        "appointment_message": "Queres agendar una visita o una llamada con un asesor?",
        "appointment_buttons": [
            {"id": "cita_visita", "title": "Agendar visita"},
            {"id": "cita_llamada", "title": "Agendar llamada"},
            {"id": "cita_no", "title": "No por ahora"}
        ],
        "completion_message": "Excelente! {name}, tu {appointment_type} quedo agendada para el {appointment_date}. Un asesor se comunicara para confirmar. Gracias!",
        "faq": {
            "direccion": "Av. Corrientes 1234, Piso 5, CABA, Buenos Aires",
            "horarios": "Lun-Vie: 9:00 - 18:00 | Sab: 10:00 - 14:00",
            "telefono": "",
            "email": "",
            "web": ""
        },
        "labels": {
            "lead": "Lead",
            "leads": "Leads",
            "appointment": "Visita",
            "agent": "Asesor"
        }
    },

    "clinica": {
        "id": "clinica",
        "name": "Clinica / Salud",
        "description": "Bot para clinicas y consultorios: turnos, especialidades, obras sociales",
        "welcome_message": "Hola! Soy el asistente virtual de {business_name}. Puedo ayudarte a sacar turno, consultar especialidades o resolver tus dudas.",
        "welcome_buttons": [
            {"id": "intent_turno", "title": "Sacar turno"},
            {"id": "intent_consulta", "title": "Hacer consulta"},
            {"id": "intent_info", "title": "Informacion"}
        ],
        "intents": ["turno", "consulta", "urgencia", "informacion"],
        "flow_steps": [
            {
                "id": "intent",
                "question": "En que podemos ayudarte?",
                "type": "buttons",
                "buttons": [
                    {"id": "intent_turno", "title": "Sacar turno"},
                    {"id": "intent_consulta", "title": "Hacer consulta"},
                    {"id": "intent_info", "title": "Informacion"}
                ],
                "field": "intent",
                "use_ai": True,
                "ai_prompt": "Clasifica la intencion: turno, consulta, urgencia, informacion"
            },
            {
                "id": "name",
                "question": "Como te llamas?",
                "type": "text",
                "field": "name"
            },
            {
                "id": "specialty",
                "question": "Que especialidad necesitas?",
                "type": "buttons",
                "buttons": [
                    {"id": "esp_general", "title": "Medicina general"},
                    {"id": "esp_oftalmo", "title": "Oftalmologia"},
                    {"id": "esp_otro", "title": "Otra especialidad"}
                ],
                "field": "custom_fields.specialty"
            },
            {
                "id": "insurance",
                "question": "Tenes obra social o prepaga?",
                "type": "buttons",
                "buttons": [
                    {"id": "os_si", "title": "Si, tengo"},
                    {"id": "os_no", "title": "No, particular"},
                    {"id": "os_consultar", "title": "Quiero consultar"}
                ],
                "field": "custom_fields.insurance"
            },
            {
                "id": "insurance_name",
                "question": "Cual es tu obra social o prepaga?",
                "type": "text",
                "field": "custom_fields.insurance_name",
                "skip_for_values": {"custom_fields.insurance": ["os_no"]}
            },
            {
                "id": "symptoms",
                "question": "Contanos brevemente el motivo de tu consulta o sintomas",
                "type": "text",
                "field": "custom_fields.symptoms"
            },
            {
                "id": "urgency",
                "question": "Que tan urgente es?",
                "type": "buttons",
                "buttons": [
                    {"id": "urg_urgente", "title": "Urgente"},
                    {"id": "urg_semana", "title": "Esta semana"},
                    {"id": "urg_puede_esperar", "title": "Puede esperar"}
                ],
                "field": "urgency"
            }
        ],
        "scoring": {
            "max_score": 10,
            "criteria": [
                {"field": "custom_fields.specialty", "points": 2, "condition": "not_empty"},
                {"field": "custom_fields.insurance", "points": 1, "condition": "not_empty"},
                {"field": "urgency", "points": 3, "condition": "equals", "value": "urgente"},
                {"field": "urgency", "points": 2, "condition": "equals", "value": "semana"},
                {"field": "custom_fields.symptoms", "points": 1, "condition": "not_empty"},
                {"field": "intent", "points": 1, "condition": "equals", "value": "turno"}
            ],
            "hot_threshold": 6,
            "warm_threshold": 3
        },
        "appointment_message": "Queres agendar un turno?",
        "appointment_buttons": [
            {"id": "cita_turno", "title": "Agendar turno"},
            {"id": "cita_llamada", "title": "Que me llamen"},
            {"id": "cita_no", "title": "No por ahora"}
        ],
        "completion_message": "{name}, tu turno quedo agendado para el {appointment_date}. Te enviaremos un recordatorio 24hs antes. Gracias!",
        "faq": {
            "direccion": "",
            "horarios": "Lun-Vie: 8:00 - 20:00 | Sab: 8:00 - 13:00",
            "telefono": "",
            "obras_sociales": "Aceptamos OSDE, Swiss Medical, Galeno, IOMA y mas",
            "urgencias": "Para urgencias llamar al numero de guardia"
        },
        "labels": {
            "lead": "Paciente",
            "leads": "Pacientes",
            "appointment": "Turno",
            "agent": "Profesional"
        }
    },

    "restaurante": {
        "id": "restaurante",
        "name": "Restaurante / Gastronomia",
        "description": "Bot para restaurantes: reservas, menu, delivery, consultas",
        "welcome_message": "Hola! Bienvenido a {business_name}. Puedo ayudarte con reservas, nuestro menu o hacer un pedido.",
        "welcome_buttons": [
            {"id": "intent_reserva", "title": "Hacer reserva"},
            {"id": "intent_menu", "title": "Ver menu"},
            {"id": "intent_delivery", "title": "Pedir delivery"}
        ],
        "intents": ["reserva", "menu", "delivery", "consulta"],
        "flow_steps": [
            {
                "id": "intent",
                "question": "Que te gustaria hacer?",
                "type": "buttons",
                "buttons": [
                    {"id": "intent_reserva", "title": "Hacer reserva"},
                    {"id": "intent_menu", "title": "Ver menu"},
                    {"id": "intent_delivery", "title": "Pedir delivery"}
                ],
                "field": "intent",
                "use_ai": True,
                "ai_prompt": "Clasifica: reserva, menu, delivery, consulta"
            },
            {
                "id": "name",
                "question": "A nombre de quien seria?",
                "type": "text",
                "field": "name"
            },
            {
                "id": "party_size",
                "question": "Para cuantas personas?",
                "type": "buttons",
                "buttons": [
                    {"id": "pers_2", "title": "2 personas"},
                    {"id": "pers_4", "title": "3-4 personas"},
                    {"id": "pers_mas", "title": "5 o mas"}
                ],
                "field": "custom_fields.party_size",
                "only_for_intents": ["reserva"]
            },
            {
                "id": "occasion",
                "question": "Es una ocasion especial?",
                "type": "buttons",
                "buttons": [
                    {"id": "oc_normal", "title": "No, casual"},
                    {"id": "oc_cumple", "title": "Cumpleanos"},
                    {"id": "oc_especial", "title": "Evento especial"}
                ],
                "field": "custom_fields.occasion",
                "only_for_intents": ["reserva"]
            },
            {
                "id": "dietary",
                "question": "Alguna preferencia alimentaria? (vegano, celiaco, alergias, etc.)",
                "type": "text",
                "field": "custom_fields.dietary"
            },
            {
                "id": "urgency",
                "question": "Para cuando seria?",
                "type": "buttons",
                "buttons": [
                    {"id": "urg_hoy", "title": "Hoy"},
                    {"id": "urg_semana", "title": "Esta semana"},
                    {"id": "urg_despues", "title": "Mas adelante"}
                ],
                "field": "urgency"
            }
        ],
        "scoring": {
            "max_score": 8,
            "criteria": [
                {"field": "custom_fields.party_size", "points": 2, "condition": "not_empty"},
                {"field": "urgency", "points": 3, "condition": "equals", "value": "hoy"},
                {"field": "urgency", "points": 2, "condition": "equals", "value": "semana"},
                {"field": "intent", "points": 1, "condition": "equals", "value": "reserva"}
            ],
            "hot_threshold": 5,
            "warm_threshold": 3
        },
        "appointment_message": "Queres confirmar tu reserva?",
        "appointment_buttons": [
            {"id": "cita_reserva", "title": "Confirmar reserva"},
            {"id": "cita_llamada", "title": "Que me llamen"},
            {"id": "cita_no", "title": "No por ahora"}
        ],
        "completion_message": "{name}, tu reserva para {appointment_date} esta confirmada! Te esperamos. Buen provecho!",
        "faq": {
            "direccion": "",
            "horarios": "Lun-Dom: 12:00 - 00:00",
            "menu": "Podes ver nuestro menu en [link]",
            "delivery": "Hacemos delivery dentro de 5km"
        },
        "labels": {
            "lead": "Cliente",
            "leads": "Clientes",
            "appointment": "Reserva",
            "agent": "Encargado"
        }
    },

    "servicios": {
        "id": "servicios",
        "name": "Servicios Generales",
        "description": "Bot generico para empresas de servicios: presupuestos, consultas, agendar",
        "welcome_message": "Hola! Soy el asistente virtual de {business_name}. En que puedo ayudarte?",
        "welcome_buttons": [
            {"id": "intent_presupuesto", "title": "Pedir presupuesto"},
            {"id": "intent_consulta", "title": "Hacer consulta"},
            {"id": "intent_agendar", "title": "Agendar reunion"}
        ],
        "intents": ["presupuesto", "consulta", "agendar", "reclamo"],
        "flow_steps": [
            {
                "id": "intent",
                "question": "En que podemos ayudarte?",
                "type": "buttons",
                "buttons": [
                    {"id": "intent_presupuesto", "title": "Pedir presupuesto"},
                    {"id": "intent_consulta", "title": "Hacer consulta"},
                    {"id": "intent_agendar", "title": "Agendar reunion"}
                ],
                "field": "intent",
                "use_ai": True,
                "ai_prompt": "Clasifica: presupuesto, consulta, agendar, reclamo"
            },
            {
                "id": "name",
                "question": "Como te llamas?",
                "type": "text",
                "field": "name"
            },
            {
                "id": "service_type",
                "question": "Que servicio te interesa?",
                "type": "text",
                "field": "custom_fields.service_type",
                "use_ai": True,
                "ai_prompt": "Extrae el tipo de servicio que necesita el usuario"
            },
            {
                "id": "description",
                "question": "Contanos un poco mas sobre lo que necesitas",
                "type": "text",
                "field": "custom_fields.description"
            },
            {
                "id": "budget_range",
                "question": "Tenes un presupuesto estimado?",
                "type": "buttons",
                "buttons": [
                    {"id": "budget_bajo", "title": "Basico"},
                    {"id": "budget_medio", "title": "Intermedio"},
                    {"id": "budget_alto", "title": "Premium"}
                ],
                "field": "custom_fields.budget_range",
                "only_for_intents": ["presupuesto"]
            },
            {
                "id": "urgency",
                "question": "Para cuando lo necesitas?",
                "type": "buttons",
                "buttons": [
                    {"id": "urg_urgente", "title": "Urgente"},
                    {"id": "urg_semana", "title": "Esta semana"},
                    {"id": "urg_mes", "title": "Este mes"},
                ],
                "field": "urgency"
            }
        ],
        "scoring": {
            "max_score": 10,
            "criteria": [
                {"field": "custom_fields.service_type", "points": 2, "condition": "not_empty"},
                {"field": "custom_fields.description", "points": 1, "condition": "not_empty"},
                {"field": "urgency", "points": 3, "condition": "equals", "value": "urgente"},
                {"field": "urgency", "points": 2, "condition": "equals", "value": "semana"},
                {"field": "intent", "points": 2, "condition": "equals", "value": "presupuesto"}
            ],
            "hot_threshold": 6,
            "warm_threshold": 3
        },
        "appointment_message": "Queres que coordinemos una reunion o llamada?",
        "appointment_buttons": [
            {"id": "cita_reunion", "title": "Agendar reunion"},
            {"id": "cita_llamada", "title": "Que me llamen"},
            {"id": "cita_no", "title": "No por ahora"}
        ],
        "completion_message": "{name}, tu {appointment_type} quedo agendada para el {appointment_date}. Nos comunicaremos para confirmar. Gracias!",
        "faq": {
            "direccion": "",
            "horarios": "Lun-Vie: 9:00 - 18:00",
            "telefono": "",
            "email": ""
        },
        "labels": {
            "lead": "Cliente",
            "leads": "Clientes",
            "appointment": "Reunion",
            "agent": "Asesor"
        }
    },

    "ecommerce": {
        "id": "ecommerce",
        "name": "E-commerce / Tienda",
        "description": "Bot para tiendas online: productos, pedidos, stock, consultas",
        "welcome_message": "Hola! Bienvenido a {business_name}. Puedo ayudarte con nuestros productos, tu pedido o resolver tus dudas.",
        "welcome_buttons": [
            {"id": "intent_productos", "title": "Ver productos"},
            {"id": "intent_pedido", "title": "Estado de pedido"},
            {"id": "intent_consulta", "title": "Hacer consulta"}
        ],
        "intents": ["productos", "pedido", "reclamo", "consulta"],
        "flow_steps": [
            {
                "id": "intent",
                "question": "En que puedo ayudarte?",
                "type": "buttons",
                "buttons": [
                    {"id": "intent_productos", "title": "Ver productos"},
                    {"id": "intent_pedido", "title": "Estado de pedido"},
                    {"id": "intent_consulta", "title": "Hacer consulta"}
                ],
                "field": "intent",
                "use_ai": True,
                "ai_prompt": "Clasifica: productos, pedido, reclamo, consulta"
            },
            {
                "id": "name",
                "question": "Como te llamas?",
                "type": "text",
                "field": "name"
            },
            {
                "id": "product_interest",
                "question": "Que producto te interesa o que estas buscando?",
                "type": "text",
                "field": "custom_fields.product_interest",
                "use_ai": True,
                "ai_prompt": "Extrae el tipo de producto o categoria que busca el usuario"
            },
            {
                "id": "budget",
                "question": "Tenes un presupuesto en mente?",
                "type": "buttons",
                "buttons": [
                    {"id": "budget_bajo", "title": "Economico"},
                    {"id": "budget_medio", "title": "Rango medio"},
                    {"id": "budget_alto", "title": "Premium"}
                ],
                "field": "custom_fields.budget_range"
            },
            {
                "id": "shipping",
                "question": "Como preferis recibirlo?",
                "type": "buttons",
                "buttons": [
                    {"id": "envio_domicilio", "title": "Envio a domicilio"},
                    {"id": "envio_retiro", "title": "Retiro en local"},
                    {"id": "envio_consultar", "title": "Consultar"}
                ],
                "field": "custom_fields.shipping_preference"
            },
            {
                "id": "urgency",
                "question": "Para cuando lo necesitas?",
                "type": "buttons",
                "buttons": [
                    {"id": "urg_hoy", "title": "Lo antes posible"},
                    {"id": "urg_semana", "title": "Esta semana"},
                    {"id": "urg_no_apura", "title": "No me apura"}
                ],
                "field": "urgency"
            }
        ],
        "scoring": {
            "max_score": 10,
            "criteria": [
                {"field": "custom_fields.product_interest", "points": 2, "condition": "not_empty"},
                {"field": "custom_fields.budget_range", "points": 1, "condition": "not_empty"},
                {"field": "urgency", "points": 3, "condition": "equals", "value": "hoy"},
                {"field": "urgency", "points": 2, "condition": "equals", "value": "semana"},
                {"field": "intent", "points": 2, "condition": "equals", "value": "productos"}
            ],
            "hot_threshold": 6,
            "warm_threshold": 3
        },
        "appointment_message": "Queres que un asesor te contacte para ayudarte?",
        "appointment_buttons": [
            {"id": "cita_llamada", "title": "Que me llamen"},
            {"id": "cita_whatsapp", "title": "Seguir por WhatsApp"},
            {"id": "cita_no", "title": "No por ahora"}
        ],
        "completion_message": "{name}, un asesor se comunicara contigo pronto para ayudarte. Gracias por tu interes!",
        "faq": {
            "envios": "Hacemos envios a todo el pais",
            "cambios": "Tenes 30 dias para cambios y devoluciones",
            "medios_pago": "Aceptamos efectivo, transferencia y tarjetas",
            "horarios": "Lun-Sab: 9:00 - 20:00"
        },
        "labels": {
            "lead": "Cliente",
            "leads": "Clientes",
            "appointment": "Contacto",
            "agent": "Vendedor"
        }
    }
}


def get_template(template_id: str) -> dict:
    """Obtiene un template por ID. Default: servicios"""
    return TEMPLATES.get(template_id, TEMPLATES["servicios"])


def get_all_templates() -> list:
    """Retorna lista resumida de todos los templates disponibles"""
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t["description"]
        }
        for t in TEMPLATES.values()
    ]
