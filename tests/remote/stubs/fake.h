#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <sys/socket.h>
typedef int esp_err_t;
enum{ESP_OK=0,ESP_FAIL=-1,ESP_ERR_NO_MEM=0x101};
typedef void *SemaphoreHandle_t;
typedef void *QueueHandle_t;
typedef void *TaskHandle_t;
#define portMAX_DELAY 0xffffffffu
#define pdTRUE 1
#define pdPASS 1
#define pdMS_TO_TICKS(x) (x)
#define MALLOC_CAP_INTERNAL 1
#define MALLOC_CAP_8BIT 2
size_t heap_caps_get_free_size(unsigned);
size_t heap_caps_get_largest_free_block(unsigned);
unsigned uxTaskGetStackHighWaterMark(TaskHandle_t);
SemaphoreHandle_t xSemaphoreCreateMutex(void);
int xSemaphoreTake(SemaphoreHandle_t,unsigned);
int xSemaphoreGive(SemaphoreHandle_t);
QueueHandle_t xQueueCreate(unsigned,unsigned);
int xQueueReset(QueueHandle_t);
int xQueueSend(QueueHandle_t,const void *,unsigned);
int xQueueReceive(QueueHandle_t,void *,unsigned);
int xQueuePeek(QueueHandle_t,void *,unsigned);
void vTaskDelay(unsigned);
int xTaskCreatePinnedToCore(void (*)(void *),const char *,unsigned,void *,unsigned,TaskHandle_t *,unsigned);
void esp_fill_random(void *,size_t);
typedef void *httpd_handle_t;
typedef struct {const char *uri;int method;const char *input;size_t content_len,cursor;const char *host,*control;char status[64];char response[65536];size_t response_len;} httpd_req_t;
typedef struct {const char *uri;int method;esp_err_t (*handler)(httpd_req_t *);} httpd_uri_t;
typedef struct {unsigned stack_size,task_priority,core_id,max_open_sockets,max_uri_handlers,max_resp_headers,backlog_conn,recv_wait_timeout,send_wait_timeout;bool lru_purge_enable;} httpd_config_t;
#define HTTPD_DEFAULT_CONFIG() ((httpd_config_t){0})
#define HTTPD_RESP_USE_STRLEN -1
#define HTTP_GET 1
#define HTTP_POST 2
esp_err_t httpd_resp_set_status(httpd_req_t *,const char *);
esp_err_t httpd_resp_set_type(httpd_req_t *,const char *);
esp_err_t httpd_resp_set_hdr(httpd_req_t *,const char *,const char *);
esp_err_t httpd_resp_send(httpd_req_t *,const char *,int);
esp_err_t httpd_resp_send_chunk(httpd_req_t *,const char *,int);
esp_err_t httpd_resp_sendstr(httpd_req_t *,const char *);
int httpd_req_get_hdr_value_str(httpd_req_t *,const char *,char *,size_t);
int httpd_req_to_sockfd(httpd_req_t *);
int httpd_req_recv(httpd_req_t *,char *,size_t);
esp_err_t httpd_start(httpd_handle_t *,const httpd_config_t *);
esp_err_t httpd_stop(httpd_handle_t);
esp_err_t httpd_register_uri_handler(httpd_handle_t,const httpd_uri_t *);
int remote_test_getsockname(int,struct sockaddr *,socklen_t *);
