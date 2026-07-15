/** @odoo-module **/

import { Component, onWillStart, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

function nowAsLocalDateTime() {
    const date = new Date();
    const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return localDate.toISOString().slice(0, 16);
}

export class ArScrapCart extends Component {
    static template = "ar_scrap.Cart";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.onSearch = this.onSearch.bind(this);
        this.onZoneChange = this.onZoneChange.bind(this);
        this.onSapFilterChange = this.onSapFilterChange.bind(this);
        this.onShiftChange = this.onShiftChange.bind(this);
        this.onProductionOrderChange = this.onProductionOrderChange.bind(this);
        this.onDateChange = this.onDateChange.bind(this);
        this.onNotesChange = this.onNotesChange.bind(this);
        this.onAttachmentsChange = this.onAttachmentsChange.bind(this);
        this.removeAttachment = this.removeAttachment.bind(this);
        this.onDefectCommentChange = this.onDefectCommentChange.bind(this);
        this.openDefectPicker = this.openDefectPicker.bind(this);
        this.closeDefectPicker = this.closeDefectPicker.bind(this);
        this.selectDefectType = this.selectDefectType.bind(this);
        this.onDefectSearch = this.onDefectSearch.bind(this);
        this.getDefectImage = this.getDefectImage.bind(this);
        this.confirmLine = this.confirmLine.bind(this);
        this.getProductCartQuantity = this.getProductCartQuantity.bind(this);
        this.addProduct = this.addProduct.bind(this);
        this.changeQuantity = this.changeQuantity.bind(this);
        this.setQuantity = this.setQuantity.bind(this);
        this.removeLine = this.removeLine.bind(this);
        this.clearCart = this.clearCart.bind(this);
        this.validateCart = this.validateCart.bind(this);
        this.showDescription = this.showDescription.bind(this);
        this.closeDescription = this.closeDescription.bind(this);
        this.formatUnitPrice = this.formatUnitPrice.bind(this);
        this.formatAmount = this.formatAmount.bind(this);
        this.formatQuantity = this.formatQuantity.bind(this);
        this.getProductLargeImage = this.getProductLargeImage.bind(this);
        this.nextCartLineId = 0;
        this.nextAttachmentId = 0;
        this.cartLinesRef = useRef("cartLines");
        this.state = useState({
            products: [],
            defectTypes: [],
            productionOrders: [],
            defectPickerLineId: false,
            defectSearch: "",
            cart: {},
            search: "",
            zoneId: "",
            sapFilter: "all",
            shift: "",
            productionOrderId: "",
            scrapDateTime: nowAsLocalDateTime(),
            notes: "",
            attachments: [],
            descriptionProduct: false,
            loading: true,
            validating: false,
        });
        onWillStart(() => this.loadProducts());
    }

    async loadProducts() {
        this.state.loading = true;
        try {
            const products = await this.orm.searchRead(
                "ar.scrap.product",
                [["active", "=", true]],
                [
                    "name",
                    "image_128",
                    "unit_price",
                    "currency_id",
                    "company_unit_price",
                    "company_currency_id",
                    "company_currency_decimal_places",
                    "description",
                    "zone_id",
                    "exists_in_sap",
                    "write_date",
                ],
                { order: "sequence, name, id" }
            );
            const productIds = products.map((product) => product.id);
            const bomLines = productIds.length ? await this.orm.searchRead(
                "ar.scrap.bom.line",
                [["product_id", "in", productIds]],
                ["product_id", "reference", "quantity", "description", "unit"],
                { order: "product_id, id" }
            ) : [];
            const bomByProduct = new Map(productIds.map((id) => [id, []]));
            for (const line of bomLines) {
                const productId = Array.isArray(line.product_id)
                    ? line.product_id[0]
                    : line.product_id?.id;
                if (bomByProduct.has(productId)) {
                    bomByProduct.get(productId).push(line);
                }
            }
            for (const product of products) {
                product.bomLines = bomByProduct.get(product.id) || [];
            }
            const defectTypes = await this.orm.searchRead(
                "ar.scrap.defect.type",
                [["active", "=", true]],
                ["name", "description", "image_128", "write_date"],
                { order: "sequence, name, id" }
            );
            this.state.defectTypes = defectTypes.filter(
                (defectType) => defectType.name.trim().toLocaleLowerCase() !== "autre"
            );
            this.state.productionOrders = await this.orm.searchRead(
                "ar.scrap.production.order",
                [["active", "=", true]],
                ["name", "quantity", "valid_from", "valid_to"],
                { order: "valid_from desc, name, id" }
            );
            this.state.products = products;
        } finally {
            this.state.loading = false;
        }
    }

    get filteredProducts() {
        const term = this.state.search.trim().toLocaleLowerCase();
        const selectedZoneId = Number(this.state.zoneId) || false;
        return this.state.products.filter((product) => {
            const bomSearchText = (product.bomLines || [])
                .map((line) => `${line.reference} ${line.description || ""}`)
                .join(" ");
            const matchesSearch = !term ||
                `${product.name} ${product.description || ""} ${bomSearchText}`
                    .toLocaleLowerCase()
                    .includes(term);
            const matchesZone = !selectedZoneId || this.getZoneId(product) === selectedZoneId;
            const matchesSap = this.state.sapFilter === "all" ||
                (this.state.sapFilter === "sap" && product.exists_in_sap) ||
                (this.state.sapFilter === "non_sap" && !product.exists_in_sap);
            return matchesSearch && matchesZone && matchesSap;
        });
    }

    get zoneOptions() {
        const zones = new Map();
        for (const product of this.state.products) {
            const id = this.getZoneId(product);
            const name = this.getZoneName(product);
            if (id && name) {
                zones.set(id, name);
            }
        }
        return [...zones.entries()]
            .map(([id, name]) => ({ id, name }))
            .sort((a, b) => a.name.localeCompare(b.name));
    }

    get cartLines() {
        return Object.values(this.state.cart);
    }

    get displayedCartLines() {
        return [...this.cartLines].reverse();
    }

    get activeDraftLine() {
        return this.cartLines.find((line) => !line.confirmed) || false;
    }

    get filteredDefectTypes() {
        const term = this.state.defectSearch.trim().toLocaleLowerCase();
        if (!term) {
            return this.state.defectTypes;
        }
        return this.state.defectTypes.filter((defectType) =>
            `${defectType.name} ${defectType.description || ""}`
                .toLocaleLowerCase()
                .includes(term)
        );
    }

    get availableProductionOrders() {
        const selectedDate = (this.state.scrapDateTime || "").slice(0, 10);
        if (!selectedDate) {
            return [];
        }
        return this.state.productionOrders.filter(
            (productionOrder) =>
                productionOrder.valid_from <= selectedDate &&
                productionOrder.valid_to >= selectedDate
        );
    }

    get allLinesConfirmed() {
        return this.cartLines.length > 0 && this.cartLines.every((line) => line.confirmed);
    }

    getProductCartQuantity(productId) {
        return this.cartLines
            .filter((line) => line.productId === productId)
            .reduce((total, line) => total + line.quantity, 0);
    }

    get totalQuantity() {
        return this.cartLines.reduce((total, line) => total + line.quantity, 0);
    }

    get totalAmount() {
        return this.cartLines.reduce(
            (total, line) => total + this.roundCurrency(
                line.quantity * line.companyUnitPrice,
                line.companyCurrencyDecimals
            ),
            0
        );
    }

    get companyCurrencyName() {
        const line = this.cartLines[0];
        return line?.companyCurrencyName || "";
    }

    getProductImage(product) {
        if (!product.image_128) {
            return false;
        }
        const unique = encodeURIComponent(product.write_date || "");
        return `/web/image/ar.scrap.product/${product.id}/image_128?unique=${unique}`;
    }

    getProductLargeImage(product) {
        if (!product?.image_128) {
            return false;
        }
        const unique = encodeURIComponent(product.write_date || "");
        return `/web/image/ar.scrap.product/${product.id}/image_1920?unique=${unique}`;
    }

    getDefectImage(defectType) {
        if (!defectType?.image_128) {
            return false;
        }
        const unique = encodeURIComponent(defectType.write_date || "");
        return `/web/image/ar.scrap.defect.type/${defectType.id}/image_128?unique=${unique}`;
    }

    getZoneId(product) {
        const zone = product.zone_id;
        if (Array.isArray(zone)) {
            return zone[0];
        }
        return zone?.id || false;
    }

    getZoneName(product) {
        const zone = product.zone_id;
        if (Array.isArray(zone)) {
            return zone[1] || "";
        }
        return zone?.display_name || zone?.name || "";
    }

    getCurrencyName(product) {
        const currency = product.currency_id;
        if (Array.isArray(currency)) {
            return currency[1] || "";
        }
        return currency?.display_name || currency?.name || "";
    }

    formatUnitPrice(record) {
        const value = Number(record.unitPrice ?? record.unit_price ?? 0);
        const currency = record.currencyName || this.getCurrencyName(record);
        return `${value.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        })} ${currency}`.trim();
    }

    roundCurrency(value, decimals = 2) {
        const factor = 10 ** decimals;
        return Math.round((Number(value || 0) + Number.EPSILON) * factor) / factor;
    }

    formatAmount(value, currency = this.companyCurrencyName, decimals = this.cartLines[0]?.companyCurrencyDecimals ?? 2) {
        return `${Number(value || 0).toLocaleString(undefined, {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        })} ${currency}`.trim();
    }

    formatQuantity(value) {
        const quantity = Number.parseFloat(value);
        return Number.isFinite(quantity) ? quantity.toFixed(3) : "0.000";
    }

    onSearch(event) {
        this.state.search = event.target.value;
    }

    onZoneChange(event) {
        this.state.zoneId = event.target.value;
    }

    onSapFilterChange(event) {
        this.state.sapFilter = event.target.value;
    }

    onShiftChange(event) {
        this.state.shift = event.target.value;
    }

    onProductionOrderChange(event) {
        this.state.productionOrderId = event.target.value;
    }

    onDateChange(event) {
        this.state.scrapDateTime = event.target.value;
        if (
            this.state.productionOrderId &&
            !this.availableProductionOrders.some(
                (productionOrder) => String(productionOrder.id) === this.state.productionOrderId
            )
        ) {
            this.state.productionOrderId = "";
            this.notification.add(
                _t("L'OF sélectionné n'est pas valide à cette nouvelle date."),
                { type: "warning", title: _t("OF réinitialisé") }
            );
        }
    }

    onNotesChange(event) {
        this.state.notes = event.target.value;
    }

    async onAttachmentsChange(event) {
        const files = Array.from(event.target.files || []);
        for (const file of files) {
            if (this.state.attachments.length >= 10) {
                this.notification.add(
                    _t("Vous ne pouvez pas joindre plus de 10 fichiers."),
                    { type: "warning", title: _t("Limite atteinte") }
                );
                break;
            }
            if (file.size > 10 * 1024 * 1024) {
                this.notification.add(
                    `${file.name} : ${_t("la taille maximale est de 10 Mo.")}`,
                    { type: "warning", title: _t("Fichier trop volumineux") }
                );
                continue;
            }
            let dataUrl;
            try {
                dataUrl = await new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = () => resolve(reader.result);
                    reader.onerror = () => reject(reader.error);
                    reader.readAsDataURL(file);
                });
            } catch {
                this.notification.add(
                    `${file.name} : ${_t("lecture du fichier impossible.")}`,
                    { type: "danger", title: _t("Erreur de fichier") }
                );
                continue;
            }
            this.state.attachments.push({
                clientId: `attachment_${++this.nextAttachmentId}`,
                name: file.name,
                mimetype: file.type || "application/octet-stream",
                size: file.size,
                data: String(dataUrl).split(",", 2)[1] || "",
            });
        }
        event.target.value = "";
    }

    removeAttachment(clientId) {
        if (this.activeDraftLine) {
            return;
        }
        this.state.attachments = this.state.attachments.filter(
            (attachment) => attachment.clientId !== clientId
        );
    }

    openDefectPicker(lineId) {
        const line = this.state.cart[lineId];
        if (!line || line.confirmed) {
            return;
        }
        this.state.defectPickerLineId = lineId;
        this.state.defectSearch = "";
    }

    closeDefectPicker() {
        this.state.defectPickerLineId = false;
        this.state.defectSearch = "";
    }

    onDefectSearch(event) {
        this.state.defectSearch = event.target.value;
    }

    selectDefectType(defectType) {
        const line = this.state.cart[this.state.defectPickerLineId];
        if (!line || line.confirmed) {
            this.closeDefectPicker();
            return;
        }
        if (defectType === "other") {
            line.defectTypeId = "other";
            line.defectTypeName = _t("Autre");
            line.defectTypeImage = false;
            line.defectTypeEmoji = "❓";
        } else {
            line.defectTypeId = String(defectType.id);
            line.defectTypeName = defectType.name;
            line.defectTypeImage = this.getDefectImage(defectType);
            line.defectTypeEmoji = "";
        }
        this.closeDefectPicker();
    }

    onDefectCommentChange(lineId, event) {
        const line = this.state.cart[lineId];
        if (line && !line.confirmed) {
            line.defectComment = event.target.value;
        }
    }

    addProduct(product) {
        if (this.activeDraftLine) {
            return;
        }
        const lineId = `line_${++this.nextCartLineId}`;
        this.state.cart[lineId] = {
            lineId,
            productId: product.id,
            name: product.name,
            unitPrice: product.unit_price,
            currencyName: this.getCurrencyName(product),
            companyUnitPrice: Number(product.company_unit_price || 0),
            companyCurrencyName: this.getCurrencyName({
                currency_id: product.company_currency_id,
            }),
            companyCurrencyDecimals: product.company_currency_decimal_places ?? 2,
            description: product.description,
            existsInSap: Boolean(product.exists_in_sap),
            defectTypeId: "",
            defectTypeName: "",
            defectTypeImage: false,
            defectTypeEmoji: "",
            defectComment: "",
            quantity: 1,
            confirmed: false,
        };
        requestAnimationFrame(() => {
            if (this.cartLinesRef.el) {
                this.cartLinesRef.el.scrollTop = 0;
            }
        });
    }

    changeQuantity(lineId, delta) {
        const line = this.state.cart[lineId];
        if (line && !line.confirmed) {
            line.quantity = Number(Math.max(0.001, line.quantity + delta).toFixed(3));
        }
    }

    setQuantity(lineId, event) {
        const line = this.state.cart[lineId];
        const quantity = Number.parseFloat(event.target.value);
        if (line && !line.confirmed && Number.isFinite(quantity) && quantity > 0) {
            line.quantity = quantity;
        } else if (line) {
            event.target.value = line.quantity;
        }
    }

    removeLine(lineId) {
        const line = this.state.cart[lineId];
        if (line && !line.confirmed) {
            delete this.state.cart[lineId];
        }
    }

    confirmLine(lineId) {
        const line = this.state.cart[lineId];
        if (!line || line.confirmed) {
            return;
        }
        if (!line.defectTypeId) {
            this.notification.add(
                _t("Sélectionnez un type de défaut."),
                { type: "warning", title: _t("Type de défaut manquant") }
            );
            return;
        }
        if (line.defectTypeId === "other" && !line.defectComment.trim()) {
            this.notification.add(
                _t("Le commentaire est obligatoire pour le type Autre."),
                { type: "warning", title: _t("Commentaire obligatoire") }
            );
            return;
        }
        if (!Number.isFinite(line.quantity) || line.quantity <= 0) {
            this.notification.add(
                _t("La quantité doit être supérieure à zéro."),
                { type: "warning", title: _t("Quantité invalide") }
            );
            return;
        }
        line.confirmed = true;
    }

    showDescription(product) {
        this.state.descriptionProduct = product;
    }

    closeDescription() {
        this.state.descriptionProduct = false;
    }

    clearCart() {
        this.state.cart = {};
        this.nextCartLineId = 0;
    }

    async validateCart() {
        if (!this.cartLines.length || this.state.validating) {
            return;
        }
        if (!this.allLinesConfirmed) {
            this.notification.add(
                _t("Confirmez la ligne en cours avant de valider la déclaration."),
                { type: "warning", title: _t("Ligne non confirmée") }
            );
            return;
        }
        if (!this.state.shift || !this.state.productionOrderId || !this.state.scrapDateTime) {
            this.notification.add(
                _t("Renseignez le Shift, l'OF et la Date avant de valider."),
                { type: "warning", title: _t("Informations manquantes") }
            );
            return;
        }
        const lineWithoutDefect = this.cartLines.find((line) => !line.defectTypeId);
        if (lineWithoutDefect) {
            this.notification.add(
                `${_t("Sélectionnez un type de défaut pour")} ${lineWithoutDefect.name}.`,
                { type: "warning", title: _t("Type de défaut manquant") }
            );
            return;
        }
        const otherWithoutComment = this.cartLines.find(
            (line) => line.defectTypeId === "other" && !line.defectComment.trim()
        );
        if (otherWithoutComment) {
            this.notification.add(
                `${_t("Ajoutez un commentaire pour le type Autre sur")} ${otherWithoutComment.name}.`,
                { type: "warning", title: _t("Commentaire obligatoire") }
            );
            return;
        }
        this.state.validating = true;
        try {
            const payload = this.cartLines.map((line) => ({
                product_id: line.productId,
                quantity: line.quantity,
                defect_type_id: line.defectTypeId,
                defect_comment: line.defectComment,
            }));
            const scrapDateTimeUtc = new Date(this.state.scrapDateTime)
                .toISOString()
                .slice(0, 19)
                .replace("T", " ");
            const result = await this.orm.call(
                "ar.scrap.order",
                "create_from_cart",
                [
                    payload,
                    this.state.shift,
                    scrapDateTimeUtc,
                    this.state.notes,
                    this.state.attachments.map(({ name, mimetype, data }) => ({ name, mimetype, data })),
                    this.state.productionOrderId,
                ]
            );
            this.clearCart();
            this.state.shift = "";
            this.state.productionOrderId = "";
            this.state.scrapDateTime = nowAsLocalDateTime();
            this.state.notes = "";
            this.state.attachments = [];
            this.nextAttachmentId = 0;
            const isDirectlyValidated = result.state === "validated";
            const message = isDirectlyValidated
                ? `${_t("Opération validée et ajoutée à l'archive")} : ${result.name}`
                : `${_t("Opération soumise au circuit de validation")} : ${result.name} (${result.state_label})`;
            this.notification.add(message, {
                type: isDirectlyValidated ? "success" : "info",
                title: isDirectlyValidated ? _t("Scrap validé") : _t("Validation requise"),
            });
        } finally {
            this.state.validating = false;
        }
    }
}

registry.category("actions").add("ar_scrap.cart", ArScrapCart);
