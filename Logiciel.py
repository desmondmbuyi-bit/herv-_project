import streamlit as st
import qrcode
import io
import os
import resend
from datetime import datetime
from supabase import create_client, Client

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Fête Foraine - Billetterie & Entrées", page_icon="🎡", layout="centered")

# --- INITIALISATION SUPABASE & RESEND ---
# En production sur Streamlit Cloud, ajoute ces clés dans les "Secrets" de ton application
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://gtmvivigmzughlyagzna.supabase.co/rest/v1/")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "sb_publishable_IXHDO2VlfOqPLcjc2RyR3g_PRXWzai9")
RESEND_API_KEY = st.secrets.get("RESEND_API_KEY", "re_SZ8dVE1a_E9Eu5pqRP83SULVv7GXeXe9g")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
resend.api_key = RESEND_API_KEY

# Mot de passe pour que n'importe qui ne puisse pas accéder à l'espace agent
MOT_DE_PASSE_AGENT = st.secrets.get("PASSWORD_AGENT", "forain2026")


# --- FONCTIONS LOGIQUE DE L'APPLICATION ---

def generer_et_envoyer_ticket(nom, email, nb_enfants, ages):
    """Génère un ticket en BDD, crée le QR code et envoie l'e-mail."""
    try:
        # 1. Insertion en base de données Supabase (Génère automatiquement un UUID)
        nouveau_ticket = {
            "nom_acheteur": nom,
            "nb_enfants": nb_enfants,
            "ages_enfants": ages,
            "statut": "valide",
            "cree_le": datetime.utcnow().isoformat()
        }
        data, count = supabase.table("tickets").insert(nouveau_ticket).execute()
        ticket_id = data[1][0]["id"]
        
        # 2. Génération du QR Code contenant l'URL Streamlit avec l'ID du ticket
        # Remplacera par l'URL finale de ton app Streamlit une fois déployée
        url_app_streamlit = st.secrets.get("APP_URL", "https://ton-app.streamlit.app")
        url_scan = f"{url_app_streamlit}/?ticket_id={ticket_id}"
        
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(url_scan)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        qr_buffer = io.BytesIO()
        img.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)
        
        # 3. Envoi du Mail via Resend
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2>🎡 Votre billet d'entrée - Fête Foraine !</h2>
                <p>Bonjour <strong>{nom}</strong>,</p>
                <p>Votre accès a bien été validé pour <strong>{nb_enfants} enfant(s)</strong>.</p>
                <p>Veuillez présenter le QR Code ci-joint à nos agents à l'entrée.</p>
                <p style='color: red;'><em>Ce ticket est à usage unique.</em></p>
            </body>
        </html>
        """
        
        resend.Emails.send({
            "from": "Billetterie Fête Foraine <billetterie@tondomaine.com>",
            "to": [email],
            "subject": "🎯 Votre ticket d'entrée Fête Foraine",
            "html": html_content,
            "attachments": [{"filename": f"ticket_{nom}.png", "content": list(qr_buffer.getvalue())}]
        })
        return True, ticket_id
    except Exception as e:
        return False, str(e)


# --- NAVIGATION PRINCIPALE (SIDEBAR) ---
st.sidebar.title("Menu Navigation")
mode = st.sidebar.radio("Choisir l'espace :", ["🛒 Vente & Enregistrement", "🛡️ Espace Agents (Entrée)"])


# =====================================================================
# ESPACE 1 : VENTE ET ENREGISTREMENT (CÔTÉ ADMIN / COMMANDE)
# =====================================================================
if mode == "🛒 Vente & Enregistrement":
    st.title("🎟️ Enregistrement des Entrées")
    st.write("Saisissez les informations de l'acheteur pour générer le ticket électronique.")
    
    with st.form("form_achat", clear_on_submit=True):
        nom = st.text_input("Nom & Prénom de l'acheteur :")
        email = st.text_input("Adresse E-mail :")
        nb_enfants = st.number_input("Nombre d'enfants :", min_value=0, step=1, value=1)
        ages_input = st.text_input("Âges des enfants (séparés par des virgules, ex: 8, 12) :")
        
        bouton_valider = st.form_submit_button("Créer le ticket et envoyer le mail")
        
        if bouton_valider:
            if not nom or not email:
                st.error("Veuillez remplir le nom et l'e-mail.")
            else:
                ages = [int(a.strip()) for a in ages_input.split(",") if a.strip().isdigit()]
                with st.spinner("Génération du ticket sécurisé..."):
                    succes, resultat = generer_et_envoyer_ticket(nom, email, nb_enfants, ages)
                    if succes:
                        st.success(f"✅ Ticket créé avec succès ! E-mail envoyé à {email}.")
                        st.info(f"ID du Ticket : {resultat}")
                    else:
                        st.error(f"Erreur lors de la création : {resultat}")


# =====================================================================
# ESPACE 2 : ESPACE AGENTS (SCAN ET VALIDATION)
# =====================================================================
elif mode == "🛡️ Espace Agents (Entrée)":
    st.title("🕵️ Contrôle des Tickets")
    
    # Sécurisation de l'accès agent
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
        st.success("Accès Agent Autorisé")
        
        # --- LOGIQUE DE LECTURE AUTOMATIQUE DU QR CODE VIA URL ---
        # Si le QR code a été scanné par l'appareil photo du téléphone, il ouvre l'URL avec ?ticket_id=...
        query_params = st.query_params
        ticket_id_scanne = query_params.get("ticket_id", None)
        
        if ticket_id_scanne:
            st.subheader("🔍 Analyse du Ticket Scanné")
            
            # Recherche du ticket dans Supabase
            res = supabase.table("tickets").select("*").eq("id", ticket_id_scanne).execute()
            
            if not res.data:
                st.error("🚨 FRAUDE : Ce ticket n'existe pas dans la base de données !")
            else:
                ticket = res.data[0]
                
                # Affichage des informations pour le contrôle d'identité
                st.markdown(f"### **Acheteur :** {ticket['nom_acheteur']}")
                st.markdown(f"### **Enfants :** {ticket['nb_enfants']}")
                st.markdown(f"**Âges enregistrés :** {', '.join(map(str, ticket['ages_enfants'])) if ticket['ages_enfants'] else 'Non spécifiés'}")
                
                if ticket["statut"] == "valide":
                    st.success("🟢 TICKET VALIDE - Contrôle d'identité en cours")
                    
                    if st.button("✅ Valider l'entrée et griller le ticket", type="primary"):
                        # Changement de statut instantané
                        supabase.table("tickets").update({
                            "statut": "utilise", 
                            "scanne_le": datetime.utcnow().isoformat()
                        }).eq("id", ticket_id_scanne).execute()
                        
                        st.success("🎉 Entrée Validée ! Le ticket est maintenant inutilisable.")
                        # Nettoyage du paramètre d'URL pour le prochain scan
                        st.query_params.clear()
                else:
                    st.error("❌ FRAUDE : Ce ticket a DEJA été utilisé !")
                    date_scan = datetime.fromisoformat(ticket['scanne_le']).strftime("%d/%m/%Y à %H:%M")
                    st.warning(f"Utilisé le : {date_scan}")
                    
            if st.button("🔄 Prêt pour un nouveau scan"):
                st.query_params.clear()
                st.rerun()
                
        else:
            st.info("Prêt à scanner. Les agents peuvent flasher le QR code directement avec l'appareil photo de leur smartphone. Cela ouvrira automatiquement cette page avec les données du client.")
            
            # Optionnel : Ajout d'un lecteur de caméra de secours directement intégré dans la page Streamlit
            st.write("---")
            st.write("📸 **Alternative : Scanner depuis cette page web**")
            # Composant HTML léger injecté pour utiliser la caméra si besoin
            st.components.v1.html("""
            <div id="reader" style="width:100%; max-width:350px; margin:auto;"></div>
            <script src="https://unpkg.com/html5-qrcode"></script>
            <script>
                function onScanSuccess(decodedText) {
                    // Redirige l'application Streamlit vers l'URL du ticket
                    window.parent.location.href = decodedText;
                }
                let html5QrcodeScanner = new Html5QrcodeScanner("reader", { fps: 10, qrbox: 250 });
                html5QrcodeScanner.render(onScanSuccess);
            </script>
            """, height=350)
