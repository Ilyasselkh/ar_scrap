/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
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
        this.onDateChange = this.onDateChange.bind(this);
        this.onNotesChange = this.onNotesChange.bind(this);
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
        this.state = useState({
            products: [],
            cart: {},
            search: "",
            zoneId: "",
            sapFilter: "all",
            shift: "",
            scrapDateTime: nowAsLocalDateTime(),
            notes: "",
            descriptionProduct: false,
            loading: true,
            validating: false,
        });
        onWillStart(() => this.loadProducts());
    }

    async loadProducts() {
        this.state.loading = true;
        try {
            this.state.products = await this.orm.searchRead(
                "ar.scrap.product",
                [["active", "=", true]],
                [
                    "name",
                    "image_128",
                    "length",
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
        } finally {
            this.state.loading = false;
        }
    }

    get filteredProducts() {
        const term = this.state.search.trim().toLocaleLowerCase();
        const selectedZoneId = Number(this.state.zoneId) || false;
        return this.state.products.filter((product) => {
            const matchesSearch = !term ||
                `${product.name} ${product.description || ""}`.toLocaleLowerCase().includes(term);
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

    onDateChange(event) {
        this.state.scrapDateTime = event.target.value;
    }

    onNotesChange(event) {
        this.state.notes = event.target.value;
    }

    addProduct(product) {
        const existing = this.state.cart[product.id];
        if (existing) {
            existing.quantity += 1;
        } else {
            this.state.cart[product.id] = {
                id: product.id,
                name: product.name,
                length: product.length,
                unitPrice: product.unit_price,
                currencyName: this.getCurrencyName(product),
                companyUnitPrice: Number(product.company_unit_price || 0),
                companyCurrencyName: this.getCurrencyName({
                    currency_id: product.company_currency_id,
                }),
                companyCurrencyDecimals: product.company_currency_decimal_places ?? 2,
                description: product.description,
                existsInSap: Boolean(product.exists_in_sap),
                quantity: 1,
            };
        }
    }

    changeQuantity(productId, delta) {
        const line = this.state.cart[productId];
        if (line) {
            line.quantity = Number(Math.max(0.001, line.quantity + delta).toFixed(3));
        }
    }

    setQuantity(productId, event) {
        const line = this.state.cart[productId];
        const quantity = Number.parseFloat(event.target.value);
        if (line && Number.isFinite(quantity) && quantity > 0) {
            line.quantity = quantity;
        } else if (line) {
            event.target.value = line.quantity;
        }
    }

    removeLine(productId) {
        delete this.state.cart[productId];
    }

    showDescription(product) {
        this.state.descriptionProduct = product;
    }

    closeDescription() {
        this.state.descriptionProduct = false;
    }

    clearCart() {
        this.state.cart = {};
    }

    async validateCart() {
        if (!this.cartLines.length || this.state.validating) {
            return;
        }
        if (!this.state.shift || !this.state.scrapDateTime) {
            this.notification.add(
                _t("Renseignez le Shift et la Date avant de valider."),
                { type: "warning", title: _t("Informations manquantes") }
            );
            return;
        }
        this.state.validating = true;
        try {
            const payload = this.cartLines.map((line) => ({
                product_id: line.id,
                quantity: line.quantity,
            }));
            const scrapDateTimeUtc = new Date(this.state.scrapDateTime)
                .toISOString()
                .slice(0, 19)
                .replace("T", " ");
            const result = await this.orm.call(
                "ar.scrap.order",
                "create_from_cart",
                [payload, this.state.shift, scrapDateTimeUtc, this.state.notes]
            );
            this.clearCart();
            this.state.shift = "";
            this.state.scrapDateTime = nowAsLocalDateTime();
            this.state.notes = "";
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
