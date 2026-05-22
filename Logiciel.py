import streamlit as st
import qrcode
import io
import os
import resend
import pandas as pd  # Ajouté pour afficher le tableau proprement
from datetime import datetime
from supabase import create_client, Client

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Fête Foraine - Billetterie & Entrées", page_icon="🎡", layout="wide") # Passage en mode 'wide' pour mieux voir le tableau

# --- INITIALISATION SUPABASE & RESEND ---
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://gtmvivigmzughlyagzna.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "sb_publishable_IXHDO2VlfOqPLcjc2RyR3g_PRXWzai9")
RESEND_API_KEY = st.secrets.get("RESEND_API_KEY", "re_SZ8dVE1a_E9Eu5pqRP83SULVv7GXeXe9g")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
resend.api_key = RESEND_API_KEY

MOT_DE_PASSE_AGENT = st.secrets.get("PASSWORD_AGENT", "forain2026")


# --- FONCTIONS LOGIQUE DE L'APPLICATION ---

def generer_et_envoyer_ticket_test(nom, email_client, nb_enfants, ages):
    """Génère le ticket en BDD et l'envoie sur ton mail de test Resend."""
    try:
        # 1. Insertion en base de données Supabase
        nouveau_ticket = {
            "nom_acheteur": nom,
            "nb_enfants": nb_enfants,
            "ages_enfants": ages,
            "statut": "valide",
            "cree_le": datetime.utcnow().isoformat()
        }
        data, count = supabase.table("tickets").insert(nouveau_ticket).execute()
        ticket_id = data[1][0]["id"]
        
        # 2. Génération du QR Code pointant vers ton site Netlify
        url_netlify_agents = "https://taupe-marigold-b86384.netlify.app" 
        url_scan = f"{url_netlify_agents}/?id={ticket_id}"
        
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(url_scan)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        qr_buffer = io.BytesIO()
        img.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)
        
        # 3. Envoi du Mail via Resend vers ton adresse de test
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <p>⚠️ <strong>INFO TRANSFERT :</strong> Ce ticket est destiné à : <strong>{email_client}</strong></p>
                <hr>
                <h2>🎡 Votre billet d'entrée - Fête Foraine !</h2>
                <p>Bonjour <strong>{nom}</strong>,</p>
                <p>Votre accès a bien été validé pour <strong>{nb_enfants} enfant(s)</strong>.</p>
                <p>Veuillez présenter le QR Code ci-joint à nos agents à l'entrée.</p>
                <p style='color: red;'><em>Ce ticket est à usage unique.</em></p>
            </body>
        </html>
        """
        
        # REMPLACE par ton adresse de connexion Resend
        MON_EMAIL_TEST = "ton-adresse-resend@gmail.com" 
        
        resend.Emails.send({
            "from": "Billetterie Fête Foraine <onboarding@resend.dev>",
            "to": [MON_EMAIL_TEST],
            "subject": f"🎯 Ticket Fête Foraine - {nom}",
            "html": html_content,
            "attachments": [{"filename": f"ticket_{nom}.png", "content": list(qr_buffer.getvalue())}]
        })
        return True, ticket_id
    except Exception as e:
        return False, str(e)


# --- NAVIGATION PRINCIPALE (SIDEBAR) ---
st.sidebar.title("Menu Navigation")
mode = st.sidebar.radio("Choisir l'espace :", [
    "🛒 Vente & Enregistrement", 
    "📊 Tableau de Bord & Suivi",
    "🛡️ Espace Agents (Entrée)"
])


# =====================================================================
# ESPACE 1 : VENTE ET ENREGISTREMENT
# =====================================================================
if mode == "🛒 Vente & Enregistrement":
    st.title("🎟️ Enregistrement des Entrées")
    st.write("Saisissez les informations de l'acheteur pour générer le ticket électronique.")
    
    with st.form("form_achat", clear_on_submit=True):
        nom = st.text_input("Nom & Prénom de l'acheteur :")
        email = st.text_input("Adresse E-mail du client :")
        nb_enfants = st.number_input("Nombre d'enfants :", min_value=0, step=1, value=1)
        ages_input = st.text_input("Âges des enfants (séparés par des virgules, ex: 8, 12) :")
        
        bouton_valider = st.form_submit_button("Créer le ticket et envoyer à ma boîte de test")
        
        if bouton_valider:
            if not nom or not email:
                st.error("Veuillez remplir le nom et l'e-mail.")
            else:
                ages = [int(a.strip()) for a in ages_input.split(",") if a.strip().isdigit()]
                with st.spinner("Génération du ticket sécurisé..."):
                    succes, resultat = generer_et_envoyer_ticket_test(nom, email, nb_enfants, ages)
                    if succes:
                        st.success(f"✅ Ticket créé dans la base ! Envoyé sur ton mail Resend.")
                        st.info(f"ID du Ticket : {resultat}")
                    else:
                        st.error(f"Erreur lors de la création : {resultat}")


# =====================================================================
# ESPACE 2 : NOUVEAU - TABLEAU DE BORD & SUIVI EN TEMPS RÉEL
# =====================================================================
elif mode == "📊 Tableau de Bord & Suivi":
    st.title("📊 Suivi des Inscriptions & Entrées")
    st.write("Voici la liste en temps réel des personnes enregistrées et leur statut d'accès.")
    
    # Bouton pour forcer le rafraîchissement des données
    if st.button("🔄 Rafraîchir les données"):
        st.rerun()

    with st.spinner("Récupération des données depuis Supabase..."):
        # Requête pour récupérer tous les tickets triés par date de création
        res = supabase.table("tickets").select("*").order("cree_le", descending=True).execute()
        
        if not res.data:
            st.info("Aucun ticket n'a encore été enregistré dans la base de données.")
        else:
            tickets = res.data
            
            # --- CALCUL DES STATISTIQUES ---
            total_tickets = len(tickets)
            total_enfants = sum([t['nb_enfants'] for t in tickets])
            utilises = sum([1 for t in tickets if t['statut'] == 'utilise'])
            non_utilises = total_tickets - utilises
            
            # Affichage des compteurs sous forme de jolies cartes
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("🎫 Total Acheteurs", total_tickets)
            col2.metric("👦 Total Enfants Attendus", total_enfants)
            col3.metric("🟢 Restent à entrer", non_utilises)
            col4.metric("🔴 Déjà à l'intérieur", utilises)
            
            st.write("---")
            
            # --- PRÉPARATION DU TABLEAU DE DONNÉES (PANDAS) ---
            # On transforme les données brutes en un tableau propre pour l'affichage
            liste_propres = []
            for t in tickets:
                # Formatage des dates pour que ce soit plus lisible
                date_creation = datetime.fromisoformat(t['cree_le'].replace('Z', '')).strftime("%d/%m/%Y à %H:%M") if t['cree_le'] else "-"
                date_scan = datetime.fromisoformat(t['scanne_le'].replace('Z', '')).strftime("%d/%m/%Y à %H:%M") if t['scanne_le'] else "Pas encore scanné"
                
                # Traduction visuelle du statut pour l'utilisateur
                statut_visuel = "🔴 DEJA ENTRE / UTILISE" if t['statut'] == 'utilise' else "🟢 VALIDE / ATTENDU"
                
                liste_propres.append({
                    "Nom de l'Acheteur": t['nom_acheteur'],
                    "Nombre d'Enfants": t['nb_enfants'],
                    "Âges": ", ".join(map(str, t['ages_enfants'])) if t['ages_enfants'] else "Non spécifiés",
                    "Statut d'Accès": statut_visuel,
                    "Enregistré le": date_creation,
                    "Scanné le (Entrée)": date_scan,
                    "ID Unique du Ticket": t['id']
                })
            
            df = pd.DataFrame(liste_propres)
            
            # Affichage du tableau interactif
            # L'utilisateur peut trier les colonnes en cliquant sur les en-têtes ou chercher un nom
            st.dataframe(
                df, 
                use_container_width=True, 
                hide_index=True
            )


# =====================================================================
# ESPACE 3 : ESPACE AGENTS (SCAN DE SECOURS SIMULÉ)
# =====================================================================
elif mode == "🛡️ Espace Agents (Entrée)":
    st.title("🕵️ Contrôle des Tickets (Secours)")
    st.warning("Cet espace sert d'historique ou de secours sur PC. Les agents utilisent normalement leur smartphone sur Netlify.")
    
    if "agent_authentifie" not in st.session_state:
        st.session_state.agent_authentifie = False
        
    if not st.session_state.agent_authentifie:
        mdp = st.text_input("Entrez le mot de passe Agent :", type="password")
        if st.button("Connexion"):
            if mdp == MOT_DE_PASSE_AGENT:
                st.session_state.agent_authentifie = True
                st.rerun()
            else:
                st.error("Mot de passe incorrect.")
    else:
        st.success("🔒 Mode Agent Actif sur PC")
        query_params = st.query_params
        ticket_id_scanne = query_params.get("ticket_id", None)
        
        if ticket_id_scanne:
            st.subheader("🔍 Analyse du Ticket")
            res = supabase.table("tickets").select("*").eq("id", ticket_id_scanne).execute()
            
            if not res.data:
                st.error("🚨 Ce ticket n'existe pas !")
            else:
                ticket = res.data[0]
                st.markdown(f"### **Acheteur :** {ticket['nom_acheteur']}")
                st.markdown(f"### **Statut :** {ticket['statut']}")
                
                if ticket["statut"] == "valide":
                    if st.button("✅ Valider l'entrée"):
                        supabase.table("tickets").update({"statut": "utilise", "scanne_le": datetime.utcnow().isoformat()}).eq("id", ticket_id_scanne).execute()
                        st.success("Entrée Validée !")
                        st.query_params.clear()
        else:
            st.info("Aucun ID de ticket détecté dans l'URL. Utilisez le tableau de bord pour suivre l'état général.")
